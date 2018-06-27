import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile


def get_sample_file(name, content=b'*'):
        with tempfile.NamedTemporaryFile() as tf:
            tf.file.write(content)
            tf.file.seek(0)
            return SimpleUploadedFile(name, tf.file.read())
