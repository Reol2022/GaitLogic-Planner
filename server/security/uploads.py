"""Small, deterministic archive admission before openpyxl/XML parsing."""
from io import BytesIO
from pathlib import PurePosixPath
import zipfile
from server.common.exceptions import BadRequestError

MAX_UPLOAD_BYTES = 2*1024*1024


async def read_upload(file):
    content = await file.read(MAX_UPLOAD_BYTES+1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise BadRequestError('导入文件不能超过 2 MB。', 'IMPORT_SIZE_LIMIT')
    return content


def validate_xlsx(content):
    if len(content) > MAX_UPLOAD_BYTES:
        raise BadRequestError('导入文件不能超过 2 MB。', 'IMPORT_SIZE_LIMIT')
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 300:
                raise ValueError()
            expanded = 0
            for member in members:
                path = PurePosixPath(member.filename)
                expanded += member.file_size
                if (member.flag_bits & 1 or path.is_absolute() or '..' in path.parts or '\\' in member.filename
                    or member.file_size > 8*1024*1024 or expanded > 24*1024*1024
                    or member.file_size > max(1, member.compress_size)*200
                    or member.filename.lower().endswith('vbaproject.bin')):
                    raise ValueError()
                if member.filename.endswith('.xml'):
                    # Bounded by ZIP limits; also check actual streamed size and
                    # DTD/entity declarations before the downstream XML parser.
                    data = archive.read(member)
                    declarations = data.upper().replace(b'\x00', b'')
                    if len(data) != member.file_size or b'<!DOCTYPE' in declarations or b'<!ENTITY' in declarations:
                        raise ValueError()
    except (ValueError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise BadRequestError('Excel 压缩结构无效或超过安全限制。', 'IMPORT_ARCHIVE_LIMIT') from None


def validate_sheet_bounds(workbook, *, max_rows=2000, max_columns=100):
    for sheet in workbook.worksheets:
        if sheet.max_row > max_rows+1 or sheet.max_column > max_columns:
            raise BadRequestError('Excel 行列数量超过安全限制。', 'IMPORT_DIMENSION_LIMIT')
