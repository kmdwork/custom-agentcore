import base64
import unittest
from types import SimpleNamespace

from invocation.request_parser import (
    extract_authenticated_request,
    extract_memory_identity,
    extract_prompt,
    validate_actor_identity,
)


class ExtractPromptTest(unittest.TestCase):
    def test_text_only_payload_is_unchanged(self):
        self.assertEqual(extract_prompt({"prompt": "Hello"}), "Hello")

    def test_image_payload_becomes_strands_content_blocks(self):
        image_bytes = b"fake png bytes"

        prompt = extract_prompt({
            "prompt": "この画像を説明してください",
            "media": {
                "type": "image",
                "format": "png",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        })

        self.assertEqual(prompt, [
            {"text": "この画像を説明してください"},
            {
                "image": {
                    "format": "png",
                    "source": {
                        "bytes": image_bytes,
                    },
                },
            },
        ])

    def test_invalid_base64_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not valid Base64"):
            extract_prompt({
                "prompt": "画像",
                "media": {
                    "type": "image",
                    "format": "jpeg",
                    "data": "not-base64",
                },
            })

    def test_unsupported_image_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "jpeg, png, or webp"):
            extract_prompt({
                "prompt": "画像",
                "media": {
                    "type": "image",
                    "format": "gif",
                    "data": base64.b64encode(b"gif").decode("ascii"),
                },
            })

    def test_image_larger_than_two_megabytes_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "2 MB or smaller"):
            extract_prompt({
                "prompt": "画像",
                "media": {
                    "type": "image",
                    "format": "jpeg",
                    "data": base64.b64encode(
                        b"x" * (2 * 1024 * 1024 + 1)
                    ).decode("ascii"),
                },
            })


class ExtractMemoryIdentityTest(unittest.TestCase):
    def test_memory_is_disabled_by_default(self):
        context = SimpleNamespace(
            session_id="00000000-0000-4000-8000-000000000001",
        )

        self.assertIsNone(extract_memory_identity({}, context))

    def test_memory_identity_uses_actor_and_runtime_session(self):
        context = SimpleNamespace(
            session_id="00000000-0000-4000-8000-000000000001",
        )

        self.assertEqual(
            extract_memory_identity(
                {"use_memory": True, "actor_id": "user-123"},
                context,
            ),
            ("user-123", "00000000-0000-4000-8000-000000000001"),
        )

    def test_actor_id_is_required_when_memory_is_enabled(self):
        context = SimpleNamespace(
            session_id="00000000-0000-4000-8000-000000000001",
        )

        with self.assertRaisesRegex(ValueError, "actor_id is required"):
            extract_memory_identity({"use_memory": True}, context)

    def test_invalid_runtime_session_id_is_rejected(self):
        context = SimpleNamespace(session_id="session id with spaces")

        with self.assertRaisesRegex(ValueError, "runtime session_id"):
            extract_memory_identity(
                {"use_memory": True, "actor_id": "user-123"},
                context,
            )


class ExtractAuthenticatedRequestTest(unittest.TestCase):
    def test_valid_laravel_authentication_is_returned(self):
        self.assertEqual(
            extract_authenticated_request({
                "authenticated_user_id": "123",
                "user_access_token": "1|sanctum-test-token",
            }),
            {
                "authenticated_user_id": "123",
                "user_access_token": "1|sanctum-test-token",
            },
        )

    def test_direct_invocation_without_laravel_authentication_is_allowed(self):
        self.assertEqual(extract_authenticated_request({}), {})

    def test_partial_authentication_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "user_access_token"):
            extract_authenticated_request({"authenticated_user_id": "123"})

    def test_invalid_user_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "authenticated_user_id"):
            extract_authenticated_request({
                "authenticated_user_id": "user-123",
                "user_access_token": "1|sanctum-test-token",
            })


class ValidateActorIdentityTest(unittest.TestCase):
    def test_authenticated_user_must_own_memory_actor(self):
        with self.assertRaisesRegex(
            ValueError,
            "actor_id does not match authenticated_user_id",
        ):
            validate_actor_identity(
                ("user-999", "session-1"),
                {
                    "authenticated_user_id": "123",
                    "user_access_token": "token",
                },
            )

    def test_matching_authenticated_user_is_allowed(self):
        validate_actor_identity(
            ("user-123", "session-1"),
            {
                "authenticated_user_id": "123",
                "user_access_token": "token",
            },
        )


if __name__ == "__main__":
    unittest.main()
