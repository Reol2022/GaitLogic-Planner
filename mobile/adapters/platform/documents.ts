import type { DocumentPort } from '../../services/downloads';
import { ApiError } from '../../services/api/client';
export const documents: DocumentPort = {
  download(options) { return uni.downloadFile(options); },
  remove(path) { try { uni.getFileSystemManager().unlink({ filePath: path, success() {}, fail() {} }); } catch { /* No path or platform diagnostic is logged. */ } },
  open(path, fileType) {
    // #ifdef WEB
    return Promise.reject(new ApiError('DOCUMENT_UNSUPPORTED', 'H5 文档打开尚未适配，请使用小程序或 App；未宣称已保存到下载目录'));
    // #endif
    // #ifndef WEB
    return new Promise<void>((resolve, reject) => { uni.openDocument({ filePath: path, fileType, showMenu: true, success() { resolve(); }, fail() { reject(new ApiError('DOCUMENT_UNSUPPORTED', '当前设备无法打开此格式，可改用 Excel 格式；文件未上传到第三方服务')); } }); });
    // #endif
  },
};
