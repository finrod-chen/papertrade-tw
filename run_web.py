"""
Web App 啟動入口
用法：py run_web.py
"""
from webapp.app import app
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print("\n" + "=" * 48)
    print("  台股紙盤交易系統 Web App")
    print(f"  瀏覽器開啟 → http://127.0.0.1:{port}")
    print("  按 Ctrl+C 停止")
    print("=" * 48 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
