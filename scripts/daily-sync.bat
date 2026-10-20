@echo off
REM moments 归档每日同步
REM 由 Windows 定时任务调用；已导入的推文会自动跳过

setlocal
cd /d "%~dp0.."

set LOG_DIR=%~dp0..\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set STAMP=%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%
set LOG=%LOG_DIR%\sync-%STAMP%.log

REM 从同目录的 sync.local.cmd 读取 MOMENTS_API / MOMENTS_TOKEN
if exist "%~dp0sync.local.cmd" call "%~dp0sync.local.cmd"

if "%MOMENTS_API%"=="" (
  echo [x] 未配置 MOMENTS_API，请先创建 scripts\sync.local.cmd >> "%LOG%"
  echo [x] 内容示例: >> "%LOG%"
  echo [x]   set MOMENTS_API=https://moments-backend.xxx.workers.dev >> "%LOG%"
  echo [x]   set MOMENTS_TOKEN=你的JWT >> "%LOG%"
  goto :end
)

echo ==== 同步开始 %date% %time% ==== > "%LOG%"
echo API: %MOMENTS_API% >> "%LOG%"

call "C:\Users\Still\.workbuddy\binaries\python\versions\3.13.12\python.exe" ^
  scripts\sync.py --author 4KAestheticHQ --all >> "%LOG%" 2>&1

echo ==== 同步结束 %date% %time% ==== >> "%LOG%"

REM 清理 30 天前日志
forfiles /p "%LOG_DIR%" /m sync-*.log /d -30 /c "cmd /c del @path" 2>nul

:end
endlocal