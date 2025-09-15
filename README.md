# ClearKey Video Streaming Demo

這是一個使用 Django + Shaka Player + ClearKey DRM 的視頻串流演示系統。

## 系統架構概述

本系統實現了完整的視頻上傳、加密、串流播放流程，使用 ClearKey DRM 保護視頻內容。

## 加密原理與邏輯

### 加密技術棧
- **Shaka Packager**: Google 開源的 DASH/HLS 打包工具
- **CENC (Common Encryption)**: 通用加密標準
- **ClearKey DRM**: W3C 標準的簡化 DRM 方案

#### Shaka Packager 支援的輸入格式
**視頻編碼器**:
- H.264 (AVC)
- H.265 (HEVC)  
- VP8, VP9
- AV1

**音頻編碼器**:
- AAC
- AC3, E-AC3
- Vorbis, Opus
- DTS

**容器格式**:
- MP4 (.mp4, .m4v, .m4a) - 通常包含 H.264/H.265
- WebM (.webm) - 通常包含 VP8/VP9
- Matroska (.mkv)
- MPEG-TS (.ts)
- FLV (.flv)

**檔案格式檢查**:
```bash
# 檢查視頻編碼器（最準確）
ffprobe -v quiet -show_entries stream=codec_name -of csv=p=0 video.mp4

# 檢查詳細資訊
mediainfo video.mp4 | grep "Codec ID"
```

**輸出格式**: 統一轉換為 DASH (.mpd + .m4s 分段)

#### DASH 格式說明

**`.mpd` (Media Presentation Description)**:
- XML 格式的 manifest 檔案
- 描述整個串流的結構：
  - 視頻品質、解析度、位元率
  - 音頻軌道資訊  
  - 分段檔案的位置和時長
  - DRM 加密資訊（KID、加密方案）
- 播放器讀取此檔案了解如何播放

**`.m4s` (Media Segment)**:
- 實際的加密媒體分段檔案
- 每段包含數秒的視頻/音頻數據
- 檔案結構範例：
  ```
  encrypted/{video_id}/
  ├── stream.mpd          (manifest檔案)
  ├── video_init.mp4      (視頻初始化)
  ├── video_1.m4s         (第1段視頻，0-4秒)
  ├── video_2.m4s         (第2段視頻，4-8秒)
  ├── audio_init.mp4      (音頻初始化，如果有)
  └── audio_1.m4s         (第1段音頻，如果有)
  ```

**分段式串流的優勢**:
- 自適應串流 - 根據網路狀況動態切換品質
- 快速啟動 - 無需等待完整檔案下載
- 暫停友好 - 只下載播放需要的分段
- DRM 保護 - 每個分段都經過加密

### Docker 配置與腳本邏輯

#### 一鍵啟動（docker compose）
- 需求：安裝 Docker 與 Docker Compose。
- 啟動：`docker compose up -d --build`
- 啟動的服務：`django`(web)、`celery`(worker)、`redis`、`packager`（供打包用的鏡像與服務）

本專案已調整為「隨開即用」：
- Celery/Django 容器掛載 `/var/run/docker.sock`，容器內安裝了 docker CLI，能呼叫宿主 Docker 啟動一次性的打包容器。
- 打包時以 `docker run --rm -v media_data:/work packager sh /work/pack.sh` 執行，與 Web 端共用同一個 named volume：`media_data`。
- 媒體資料夾 volume 名稱固定為 `media_data`，確保 compose 與任務一致。

可能的權限問題：若看到「permission denied on /var/run/docker.sock」，請將使用者加入 `docker` 群組或調整 docker.sock 權限。

#### Dockerfile 結構
```dockerfile
FROM google/shaka-packager:latest
WORKDIR /work
COPY pack.sh /work/pack.sh
RUN chmod +x /work/pack.sh
```

#### pack.sh 腳本邏輯
1. **環境準備**: 設定輸入/輸出路徑，取得 KID_HEX 和 KEY_HEX 環境變數
2. **雙軌道嘗試**: 先嘗試處理視頻+音頻軌道
   - 分別為視頻和音頻軌道設定加密標籤 (SD, AUDIO)
   - 使用相同的 KID/KEY 對進行加密
   - 產生分段檔案 (`video_*.m4s`, `audio_*.m4s`) 和初始化檔案
3. **備用方案**: 如果雙軌道失敗（通常是沒有音軌），降級為僅視頻軌道
4. **輸出**: 產生 DASH manifest (`stream.mpd`) 和加密的媒體分段

#### 關鍵參數說明
- `--enable_raw_key_encryption`: 啟用原始金鑰加密模式
- `--protection_scheme=cenc`: 使用 CENC 加密標準
- `--generate_static_live_mpd`: 產生靜態 DASH manifest

## 後端流程

### 1. 視頻上傳 (VideoForm)
```python
def save(self, commit=True):
    instance = super().save(commit=commit)
    if commit:
        transaction.on_commit(lambda: encrypt_video.delay(instance.id))
    return instance
```

### 2. 異步加密處理 (Celery Task)
1. **金鑰生成**: 如果 `kid_hex`/`key_hex` 不存在，生成 16 字節隨機金鑰
2. **Docker 執行**: 
   ```bash
   docker run --rm --platform linux/amd64 \
     -v {output_dir}:/work/out \
     -v {input_file}:/work/input/input.mp4:ro \
     -e KID_HEX={kid} -e KEY_HEX={key} \
     packager sh /work/pack.sh
   ```
3. **狀態更新**: 成功後將視頻狀態設為 'READY'，失敗則標記為 'failed'

### 3. API 端點
- `GET /` - 視頻列表頁
- `GET /video/<id>/` - 視頻播放頁
- `GET /license/<id>/` - ClearKey 許可證 API

### 4. 許可證服務器
```python
def license_api(request, video_id):
    # 將 hex 格式轉換為 base64url (ClearKey 標準)
    kid_b64url = hex_to_base64url(video.kid_hex)
    key_b64url = hex_to_base64url(video.key_hex)
    
    return JsonResponse({
        "keys": [{
            "kty": "oct",
            "kid": kid_b64url,
            "k": key_b64url
        }]
    })
```

## 前端流程與播放器解密

### 1. 視頻列表展示
- 查詢狀態為 'READY' 的視頻
- 網格式卡片佈局顯示可播放視頻
- 點擊跳轉到播放頁面

### 2. Shaka Player 初始化
```javascript
// 1. 獲取許可證數據
const licenseResponse = await fetch('/license/{video_id}/');
const licenseData = await licenseResponse.json();

// 2. 配置 ClearKey
const clearKeys = {};
licenseData.keys.forEach(key => {
    clearKeys[key.kid] = key.k;
});

player.configure({
    drm: {
        clearKeys: clearKeys
    }
});

// 3. 載入加密的 DASH manifest
await player.load('/media/encrypted/{id}/stream.mpd');
```

### 3. 解密過程
1. **Manifest 解析**: Shaka Player 讀取 `.mpd` 檔案，識別加密資訊
2. **金鑰映射**: 使用 `clearKeys` 配置將 KID 映射到對應的解密金鑰
3. **即時解密**: 播放器下載加密分段時，使用對應金鑰即時解密
4. **媒體播放**: 解密後的媒體數據直接送到瀏覽器進行播放

## 安全性分析：這樣的前端配置能擋什麼樣的人？

### ✅ 能夠防護的對象
1. **一般用戶**: 無法直接下載完整的未加密視頻檔案
2. **初級爬蟲**: 簡單的下載工具無法取得可播放的視頻
3. **偶然發現者**: 瀏覽檔案系統時看到的是加密分段，無法直接播放

### ⚠️ 無法防護的對象
1. **開發者**: 
   - 可以查看前端 JavaScript 程式碼
   - 能夠發現許可證 API 端點
   - 可以直接呼叫 `/license/<id>/` 取得解密金鑰

2. **技術熟練的用戶**:
   - 使用瀏覽器開發者工具監控網路請求
   - 可以擷取 manifest 和金鑰資訊
   - 能夠重組並解密視頻內容

3. **自動化工具**:
   - 可以模擬瀏覽器行為
   - 能夠自動擷取許可證和媒體分段
   - 可以批量下載並解密內容

### 安全建議
ClearKey DRM 主要適用於：
- **開發測試環境**
- **內部系統或受信任環境**
- **低價值內容保護**

如需更強的保護，建議升級到：
- **Widevine** (Google)
- **PlayReady** (Microsoft)  
- **FairPlay** (Apple)

這些方案提供硬體級別的金鑰保護，但實作複雜度較高。

## 執行方式

需要開啟兩個terminal，一個用來啟動後端服務，一個是部署celery
1. 安裝專案所需套件
   ```
   cd clearkey-demo
   cd backend
   poetry install
   ```
2. 進入虛擬環境（2個terminal都要）:
   ```
   poetry shell
   ```
3. 其中一個terminal啟動後端服務:
   ```bash
   cd bac
   python manage.py runserver
   ```
4. 另一個terminal啟動celery:
   ```
   celery -A server worker -l info
   ```

5. 訪問 `http://localhost:8000` 查看影片庫，訪問`http://localhost:8000/admin`，可以

6. 上傳mp4或是webm後，系統會自動進行加密處理，完成後即可播放
