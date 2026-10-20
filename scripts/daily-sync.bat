@echo off
REM moments 归档每日同步：复制媒体 -> 写 D1 -> 构建 -> 部署 Pages
REM 已导入的推文会自动跳过

setlocal
cd /d "%~dp0.."

set LOG_DIR=%~dp0..\logs
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set STAMP=%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%
set LOG=%LOG_DIR%\sync-%STAMP%.log

if exist "%~dp0sync.local.cmd" call "%~dp0sync.local.cmd"

if "%MOMENTS_API%"=="" (
  echo [x] 未配置 MOMENTS_API >> "%LOG%"
  echo [x] 请复制 sync.local.cmd.example 为 sync.local.cmd 并填入 >> "%LOG%"
  goto :end
)

echo ==== 同步开始 %date% %time% ==== > "%LOG%"

REM 1. 复制媒体到 frontend/public/media 并写入 D1
call "C:\Users\Still\.workbuddy\binaries\python\versions\3.13.12\python.exe" ^
  scripts\sync.py --author 4KAestheticHQ --all >> "%LOG%" 2>&1

REM 2. 构建前端（媒体会随构建产物一起打包）
echo ---- 构建前端 ---- >> "%LOG%"
cd frontend
call npm run build >> "%LOG%" 2>&1

REM 3. 部署到 Pages
echo ---- 部署 Pages ---- >> "%LOG%"
call npx wrangler pages deploy .output/public --project-name moments-gallery >> "%LOG%" 2>&1

echo ==== 同步结束 %date% %time% ==== >> "%LOG%"

REM 清理 30 天前日志
forfiles /p "%LOG_DIR%" /m sync-*.log /d -30 /c "cmd /c del @path" 2>nul

:end
endlocal