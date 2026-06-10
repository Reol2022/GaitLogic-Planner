import request from "./request";
import type { ExcelImportResult } from "@/types/models";

export const EXCEL_TEMPLATE_FILENAME = "gaitlogic_planner_template.xlsx";

export function downloadExcelTemplate() {
  return request.get<Blob>("/excel/template", {
    responseType: "blob",
  });
}

export function importExcelFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return request.post<ExcelImportResult>("/excel/import", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
}
