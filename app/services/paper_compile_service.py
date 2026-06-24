import shutil
import subprocess
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from sqlalchemy import select

from app.db import db
from app.models.compile_job import ALLOWED_LATEX_COMPILERS, CompileJob
from app.models.paper import Paper
from app.models.paper_file import PaperFile
from app.storage import get_file, store_file_at_key


MAX_COMPILE_FILE_SIZE = 25 * 1024 * 1024
MAX_COMPILE_PROJECT_SIZE = 100 * 1024 * 1024
MAX_LOG_CHARS = 200_000


class PaperCompileService:
    def __init__(self, settings):
        self.settings = settings

    def create_compile_job(self, session, paper):
        compiler = self._compiler_for(paper)
        job = CompileJob(
            paper_id=paper.id,
            status="pending",
            compiler=compiler,
            builder="latexmk",
            main_file=self._main_file_for(paper),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    def compile_job(self, job_id):
        session = db.session()
        workspace = None
        try:
            job = session.get(CompileJob, job_id)
            if job is None:
                return

            paper = session.get(Paper, job.paper_id)
            if paper is None:
                return

            workspace = self._workspace_for(paper, job)
            self._mark_running(session, job)
            paper_files = session.execute(select(PaperFile).where(PaperFile.paper_id == paper.id)).scalars().all()
            source_dir = workspace / "source"
            source_dir.mkdir(parents=True, exist_ok=True)

            self._download_project_files(paper_files, source_dir)
            main_file = self._main_file_for(paper)
            job.main_file = main_file
            if not (source_dir / main_file).is_file():
                self._mark_failed(session, job, f"Main file not found: {main_file}", logs=f"Main file not found: {main_file}")
                return

            result = self._run_latexmk(job, source_dir)
            logs = self._combined_logs(result)
            log_key = self._upload_text_artifact(paper, job, "compile.log", logs, "text/plain")
            job.log_key = log_key
            job.logs = self._truncate_logs(logs)

            if result.returncode != 0:
                self._mark_failed(session, job, "Compilation failed.", logs=job.logs)
                return

            pdf_path = source_dir / "build" / f"{Path(main_file).stem}.pdf"
            if not pdf_path.is_file():
                self._mark_failed(session, job, "Compilation finished but no PDF was generated.", logs=job.logs)
                return

            pdf_key = self._upload_bytes_artifact(
                paper,
                job,
                "output.pdf",
                pdf_path.read_bytes(),
                "application/pdf",
            )
            now = datetime.now(timezone.utc)
            job.output_pdf_key = pdf_key
            job.status = "success"
            job.error_message = None
            job.finished_at = now
            paper.data = {
                **(paper.data or {}),
                "main_file": main_file,
                "compiler": job.compiler,
                "builder": job.builder,
                "output_dir": "build",
                "latest_compile_job_id": job.id,
                "latest_pdf_key": pdf_key,
                "last_compiled_at": now.isoformat(),
            }
            session.commit()
        except subprocess.TimeoutExpired as error:
            logs = self._timeout_logs(error)
            self._mark_failed(session, job, "Compilation timed out.", logs=logs)
        except Exception as error:
            if "job" in locals() and job is not None:
                self._mark_failed(session, job, f"Compilation failed: {error}", logs=str(error))
        finally:
            session.close()
            if workspace is not None:
                shutil.rmtree(workspace, ignore_errors=True)

    def _download_project_files(self, paper_files, source_dir):
        total_size = 0
        for paper_file in paper_files:
            target_path = self._target_path(source_dir, paper_file.path)
            response = get_file(self.settings, paper_file.storage_key)
            body = response["Body"].read()
            size = len(body)
            if size > MAX_COMPILE_FILE_SIZE:
                raise ValueError(f"File too large for compile: {paper_file.path}")
            total_size += size
            if total_size > MAX_COMPILE_PROJECT_SIZE:
                raise ValueError("Project is too large to compile.")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(body)

    def _target_path(self, source_dir, project_path):
        normalized = self._normalized_project_path(project_path)
        parts = normalized.parts
        if parts and parts[0] == "source":
            parts = parts[1:]
        relative_path = PurePosixPath(*parts)
        target_path = (source_dir / Path(*relative_path.parts)).resolve()
        source_root = source_dir.resolve()
        if source_root != target_path and source_root not in target_path.parents:
            raise ValueError(f"Invalid project path: {project_path}")
        return target_path

    def _normalized_project_path(self, project_path):
        if "\x00" in str(project_path):
            raise ValueError("Invalid project path.")
        parsed = PurePosixPath(str(project_path).replace("\\", "/"))
        if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
            raise ValueError(f"Invalid project path: {project_path}")
        return parsed

    def _run_latexmk(self, job, source_dir):
        command = self._latexmk_command(job)
        timeout = int(getattr(self.settings, "LATEX_COMPILE_TIMEOUT_SECONDS", 60) or 60)
        return subprocess.run(
            command,
            cwd=source_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )

    def _latexmk_command(self, job):
        compiler_flags = {
            "pdflatex": "-pdf",
            "xelatex": "-xelatex",
            "lualatex": "-lualatex",
        }
        return [
            "latexmk",
            compiler_flags[job.compiler],
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-outdir=build",
            job.main_file,
        ]

    def _mark_running(self, session, job):
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(job)

    def _mark_failed(self, session, job, message, logs=None):
        job.status = "failed"
        job.error_message = message
        job.logs = self._truncate_logs(logs or message)
        job.finished_at = datetime.now(timezone.utc)
        session.commit()

    def _upload_text_artifact(self, paper, job, filename, content, content_type):
        return self._upload_bytes_artifact(paper, job, filename, content.encode("utf-8"), content_type)

    def _upload_bytes_artifact(self, paper, job, filename, body, content_type):
        key = f"papers/{paper.id}/builds/{job.id}/{filename}"
        upload = SimpleNamespace(filename=filename, content_type=content_type, file=BytesIO(body))
        stored = store_file_at_key(upload, self.settings, key, filename=filename)
        return stored["key"]

    def _combined_logs(self, result):
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if stdout and stderr:
            return f"{stdout}\n{stderr}"
        return stdout or stderr

    def _timeout_logs(self, error):
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        return self._truncate_logs(f"{stdout}\n{stderr}\nCompilation timed out.")

    def _truncate_logs(self, logs):
        if logs is None:
            return None
        if len(logs) <= MAX_LOG_CHARS:
            return logs
        return logs[-MAX_LOG_CHARS:]

    def _workspace_for(self, paper, job):
        root = Path(getattr(self.settings, "LATEX_TMP_ROOT", "/tmp/papers") or "/tmp/papers")
        return root / paper.id / job.id

    def _main_file_for(self, paper):
        main_file = str((paper.data or {}).get("main_file") or "main.tex").strip() or "main.tex"
        normalized = self._normalized_project_path(main_file)
        if normalized.parts and normalized.parts[0] == "source":
            normalized = PurePosixPath(*normalized.parts[1:])
        return str(normalized)

    def _compiler_for(self, paper):
        compiler = str((paper.data or {}).get("compiler") or getattr(self.settings, "LATEX_DEFAULT_COMPILER", "pdflatex"))
        return compiler if compiler in ALLOWED_LATEX_COMPILERS else "pdflatex"
