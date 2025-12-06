#!/bin/bash
# Скрипт для показа ошибок каждого промпта

echo "=== Ошибки по промптам (сравнение с v7) ==="
echo ""

for prompt in items_v2 items_v3 items_v4 items_v5 items_v7 items_v8 items_v9 items_v10; do
    echo "### $prompt.txt ###"
    
    # Ищем файлы этого промпта
    files=$(find output -name "*${prompt}*test*.json" -o -name "*${prompt}*.json" | grep -v "v10" 2>/dev/null)
    
    if [ -z "$files" ]; then
        echo "  Файлы не найдены"
        echo ""
        continue
    fi
    
    # Для каждого файла показываем ошибки
    for file in $files; do
        # Проверяем, что это сравнение с v7
        ref=$(jq -r '.test_results.reference_file // ""' "$file" 2>/dev/null)
        if [[ "$ref" != *"v7"* ]] && [[ "$ref" != "" ]]; then
            continue
        fi
        
        errors=$(jq -r '.test_results.errors // "no_test"' "$file" 2>/dev/null)
        
        if [ "$errors" != "no_test" ] && [ "$errors" != "null" ]; then
            echo "  Файл: $(basename $file)"
            echo "  Ошибок: $errors"
            
            # Показываем все ошибки
            jq -r '.test_results.all_errors[]? | "    Строка \(.line // "header"): \(.field) = \"\(.expected)\" vs \"\(.actual)\""' "$file" 2>/dev/null
            echo ""
        fi
    done
    echo ""
done
