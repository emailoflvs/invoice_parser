"""Утилиты для сравнения JSON"""
import logging
import re
from decimal import Decimal
from datetime import date, datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

def normalize_value(value: Any) -> Any:
    """Нормализация значения для сравнения"""
    if value is None:
        return None
    if isinstance(value, str):
        # Убираем пробелы и приводим к lowercase для сравнения
        normalized = value.strip().lower()
        # Нормализуем числа в строках (убираем пробелы между цифрами)
        normalized = re.sub(r'(\d)\s+(\d)', r'\1\2', normalized)
        # Нормализуем валюты
        if normalized in ['грн', 'грн.', 'uah']:
            return 'uah'
        # Нормализуем даты
        date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', normalized)
        if date_match:
            return normalized
        return normalized
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value

def compare_values(expected: Any, actual: Any, tolerance: Decimal = Decimal('0.01')) -> bool:
    """Сравнение значений с учетом нормализации"""
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    
    # Нормализуем оба значения
    exp_norm = normalize_value(expected)
    act_norm = normalize_value(actual)
    
    # Сравнение чисел с допуском
    if isinstance(exp_norm, Decimal) and isinstance(act_norm, Decimal):
        return abs(exp_norm - act_norm) <= tolerance
    
    # Сравнение строк
    if isinstance(exp_norm, str) and isinstance(act_norm, str):
        return exp_norm == act_norm
    
    return exp_norm == act_norm

def compare_json(expected: Dict[str, Any], actual: Dict[str, Any], path: str = "") -> Dict[str, Any]:
    """
    Сравнение двух JSON структур
    
    Args:
        expected: Ожидаемая структура
        actual: Фактическая структура
        path: Текущий путь в структуре (для сообщений об ошибках)
        
    Returns:
        Словарь с результатами сравнения:
        - match: bool - совпадают ли структуры
        - accuracy: float - точность совпадения (0-1)
        - differences: list - список различий
    """
    # Служебные поля, которые игнорируются при сравнении
    IGNORED_FIELDS = {
        'model', 'timestamp', 'source_file', 'pages', 'tables', 
        'fields', 'raw_block', 'header'  # Игнорируем дубликаты данных
    }
    
    differences = []
    match = True
    
    def _compare_recursive(exp: Any, act: Any, current_path: str):
        nonlocal match
        
        if isinstance(exp, dict) and isinstance(act, dict):
            # Сравнение словарей
            all_keys = set(exp.keys()) | set(act.keys())
            for key in all_keys:
                # Пропускаем служебные поля
                if key in IGNORED_FIELDS:
                    continue
                    
                new_path = f"{current_path}.{key}" if current_path else key
                if key not in exp:
                    differences.append({
                        "path": new_path,
                        "type": "missing_in_expected",
                        "expected": None,
                        "actual": act[key]
                    })
                    match = False
                elif key not in act:
                    differences.append({
                        "path": new_path,
                        "type": "missing_in_actual",
                        "expected": exp[key],
                        "actual": None
                    })
                    match = False
                else:
                    _compare_recursive(exp[key], act[key], new_path)
                    
        elif isinstance(exp, list) and isinstance(act, list):
            # Сравнение списков
            max_len = max(len(exp), len(act))
            for i in range(max_len):
                new_path = f"{current_path}[{i}]"
                if i >= len(exp):
                    differences.append({
                        "path": new_path,
                        "type": "missing_in_expected",
                        "expected": None,
                        "actual": act[i]
                    })
                    match = False
                elif i >= len(act):
                    differences.append({
                        "path": new_path,
                        "type": "missing_in_actual",
                        "expected": exp[i],
                        "actual": None
                    })
                    match = False
                else:
                    _compare_recursive(exp[i], act[i], new_path)
        else:
            # Сравнение примитивных значений
            exp_norm = normalize_value(exp)
            act_norm = normalize_value(act)
            if not compare_values(exp_norm, act_norm):
                differences.append({
                    "path": current_path,
                    "type": "mismatch",
                    "expected": exp,
                    "actual": act
                })
                match = False
    
    _compare_recursive(expected, actual, path)
    
    # Вычисление точности
    total_fields = _count_fields(expected)
    if total_fields > 0:
        accuracy = 1.0 - (len(differences) / total_fields)
    else:
        accuracy = 1.0 if match else 0.0
    
    return {
        "match": match,
        "accuracy": max(0.0, min(1.0, accuracy)),
        "differences": differences
    }

def _count_fields(data: Any) -> int:
    """Подсчет количества полей в структуре"""
    if isinstance(data, dict):
        return sum(1 + _count_fields(v) for v in data.values())
    elif isinstance(data, list):
        return sum(_count_fields(item) for item in data)
    else:
        return 1
