@echo off
chcp 65001 >nul
title Easy AI Shell - AGI Enhanced
cd /d "%~dp0."
echo ================================
echo    Easy AI Shell - AGI增强版 启动中...
echo ================================
echo.
echo 启动时间: %date% %time%
echo ================================
if not exist "agi_config.json" (
    echo 创建默认AGI配置文件...
    python -c "import json; config = {^
        'agi_growth': {^
            'enabled': True,^
            'debug_mode': False,^
            'log_level': 'INFO'^
        }^
    }; open('agi_config.json', 'w', encoding='utf-8').write(json.dumps(config, ensure_ascii=False, indent=2))"
    echo.
)
python easy_ai_shell.py -w "%~dp0." 2>&1 | tee "%~dp0easy-ai-files\output.log"
pause
