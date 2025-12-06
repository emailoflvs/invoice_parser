#!/bin/bash
echo "# Детальные результаты тестирования v8, v9, v10"
echo "## Модель: gemini-2.5-pro"
echo "## Эталон: gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json"
echo ""

for prompt_file in output/dnipromash_gemini-2.5-pro_12061959_8errors.json output/dnipromash_gemini-2.5-pro_12062003_8errors.json output/dnipromash_gemini-2.5-pro_12062006_8errors.json; do
    prompt=$(jq -r '.prompt' "$prompt_file")
    echo "## $prompt (gemini-2.5-pro)"
    echo ""
    
    jq -r '.tests[] | 
        "### ПАРСИНГ \(.test_num): \(.timestamp | split("T")[1] | split(".")[0]) (\(.errors) ошибки)\n\n| № | Раздел | Поле | Ожидается | Получено |\n|---|--------|------|-----------|----------|\n" + 
        (.test_results.all_differences[] | "| \(.line // "header") | \(.path) | \(.expected) | \(.actual) |") + "\n"'
        "$prompt_file"
    echo ""
done
