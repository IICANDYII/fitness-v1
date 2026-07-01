@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ============================================================
REM  视频版识别流水线 - 直接发送低码率视频片段给 LLM
REM ============================================================
REM
REM  用法：
REM    run_video_pipeline.bat <视频路径>
REM    run_video_pipeline.bat <视频路径> --overwrite
REM    run_video_pipeline.bat <视频路径> -o <输出目录>
REM    run_video_pipeline.bat <视频路径> -w 2
REM
REM  示例：
REM    run_video_pipeline.bat D:\videos\workout.mp4
REM    run_video_pipeline.bat gym_analyzer\input\8\video.mp4 --overwrite
REM
REM  前置条件：
REM    1. 安装 ffmpeg 并确保其在 PATH 中
REM    2. 配置 .env 文件中的 NEXTROUTER_API_KEY
REM    3. 如需光流辅助，先用 extractor 抽帧：
REM       python -m gym_analyzer.extractor <视频路径>
REM
REM  输出目录默认：recognize\visualize\result\v_video\<视频名>\
REM ============================================================

if "%~1"=="" (
    echo 用法: run_video_pipeline.bat ^<视频路径^> [选项]
    echo.
    echo 选项:
    echo   --overwrite       忽略缓存，重新执行所有步骤
    echo   -o ^<输出目录^>     指定结果输出目录
    echo   -w ^<并发数^>       Phase 2 并发数（默认 4）
    echo.
    echo 示例:
    echo   run_video_pipeline.bat D:\videos\workout.mp4
    echo   run_video_pipeline.bat D:\videos\workout.mp4 --overwrite -w 2
    exit /b 1
)

echo.
echo ============================================================
echo  视频版健身动作识别流水线
echo ============================================================
echo  视频: %~1
echo  参数: %*
echo ============================================================
echo.

REM 检查 ffmpeg
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 ffmpeg，请先安装：
    echo   winget install ffmpeg
    echo   或 choco install ffmpeg
    exit /b 1
)

REM 切换到项目根目录
cd /d "%~dp0"

REM 运行视频流水线
python -m gym_analyzer.pipeline_video %*

if errorlevel 1 (
    echo.
    echo [错误] 流水线执行失败
    exit /b 1
)

echo.
echo [完成] 识别结果已保存
