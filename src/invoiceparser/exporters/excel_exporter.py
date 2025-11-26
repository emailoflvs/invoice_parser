"""Экспорт в Excel"""
import logging
from pathlib import Path
from openpyxl import Workbook
from ..core.config import Config
from ..core.models import InvoiceData

logger = logging.getLogger(__name__)

class ExcelExporter:
    """Экспортер в Excel формат"""
    
    def __init__(self, config: Config):
        """
        Инициализация экспортера
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.output_dir = config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export(self, document_path: Path, invoice_data: InvoiceData) -> Path:
        """
        Экспорт данных счета в Excel
        
        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета
            
        Returns:
            Путь к созданному Excel файлу
        """
        # Генерируем имя файла на основе исходного документа
        filename_base = document_path.stem
        output_path = self.output_dir / f"{filename_base}.xlsx"
        
        wb = Workbook()
        if 'Sheet' in wb.sheetnames:
            wb.remove(wb['Sheet'])
        
        # Header sheet
        ws1 = wb.create_sheet("Реквизиты")
        ws1['A1'], ws1['B1'] = "Поле", "Значение"
        header_dict = invoice_data.header.model_dump()
        row = 2
        for key, value in header_dict.items():
            ws1[f'A{row}'] = key
            ws1[f'B{row}'] = str(value) if value is not None else ""
            row += 1
        
        # Items sheet
        ws2 = wb.create_sheet("Позиции")
        if invoice_data.items:
            headers = list(invoice_data.items[0].model_dump().keys())
            for col_idx, header in enumerate(headers, start=1):
                ws2.cell(row=1, column=col_idx, value=header)
            for row_idx, item in enumerate(invoice_data.items, start=2):
                item_dict = item.model_dump()
                for col_idx, header in enumerate(headers, start=1):
                    value = item_dict.get(header)
                    ws2.cell(row=row_idx, column=col_idx, value=str(value) if value is not None else "")
        
        wb.save(output_path)
        logger.info(f"Excel exported: {output_path.name}")
        return output_path
