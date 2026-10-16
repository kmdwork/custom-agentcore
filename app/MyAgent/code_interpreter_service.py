import hashlib
import mimetypes
import os
import re
import uuid
from pathlib import PurePosixPath

import boto3
from strands import tool
from strands_tools.code_interpreter import AgentCoreCodeInterpreter


AWS_REGION = "ap-northeast-1"
DOWNLOAD_URL_EXPIRES_IN = 600
MAX_ARTIFACT_BYTES = 25 * 1024 * 1024
SAFE_FILE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _validate_file_name(file_name: str) -> None:
    if SAFE_FILE_NAME.fullmatch(file_name) is None:
        raise ValueError(
            "file name must use lowercase English letters, numbers, dots, "
            "hyphens, or underscores only"
        )


class CodeInterpreterService:
    def __init__(self, session_id: str, actor_id: str):
        session_key = f"{actor_id}\0{session_id}".encode("utf-8")
        self.scope_id = hashlib.sha256(session_key).hexdigest()[:32]
        self.session_name = f"ci-{self.scope_id}"

        self.code_interpreter = AgentCoreCodeInterpreter(
            region=AWS_REGION,
            session_name=self.session_name,
            auto_create=True,
            persist_sessions=True,
        )

    @tool
    def publish_generated_file(self, path: str) -> dict:
        """Upload a generated Code Interpreter file to S3 and return a temporary download URL.

        The path must be relative and located under the artifacts directory,
        for example `artifacts/report.xlsx`.
        """
        artifact_path = PurePosixPath(path)
        if artifact_path.is_absolute() or ".." in artifact_path.parts:
            raise ValueError("path must be a safe relative path")
        if not artifact_path.parts or artifact_path.parts[0] != "artifacts":
            raise ValueError("path must be under the artifacts directory")

        file_name = artifact_path.name
        _validate_file_name(file_name)

        session_name, error = self.code_interpreter._ensure_session(self.session_name)
        if error:
            raise RuntimeError(str(error))

        client = self.code_interpreter._sessions[session_name].client
        content = client.download_file(path)
        body = content.encode("utf-8") if isinstance(content, str) else content

        if len(body) > MAX_ARTIFACT_BYTES:
            raise ValueError("generated file must not exceed 25 MiB")

        bucket = os.environ.get("GENERATED_FILES_BUCKET")
        if not bucket:
            raise RuntimeError("GENERATED_FILES_BUCKET is not configured")

        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        object_key = f"artifacts/{self.scope_id}/{uuid.uuid4().hex}/{file_name}"

        s3 = boto3.client("s3", region_name=AWS_REGION)
        s3.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=body,
            ContentType=content_type,
        )

        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
                "ResponseContentDisposition": f'attachment; filename="{file_name}"',
            },
            ExpiresIn=DOWNLOAD_URL_EXPIRES_IN,
        )

        return {
            "name": file_name,
            "content_type": content_type,
            "size": len(body),
            "url": url,
            "expires_in": DOWNLOAD_URL_EXPIRES_IN,
        }


def create_code_interpreter_tools(session_id: str, actor_id: str) -> list:
    """Create file-generation tools isolated to one user session."""
    service = CodeInterpreterService(session_id, actor_id)
    return [
        service.code_interpreter.code_interpreter,
        service.publish_generated_file,
    ]
