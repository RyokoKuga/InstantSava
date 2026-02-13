# InstantSava

複雑な設定は一切不要で、誰でも簡単に「今すぐ」ローカルサーバーを立ち上げることができます。

## ダウンロード
ビルド済みのバイナリは [**Releases**](https://github.com/RyokoKuga/InstantSava/releases) から入手できます。
* **Windows**: `.exe`
* **macOS**: `.app`

## 使い方
1. **起動**: アプリを実行します。
2. **設定**: `⚙ Preferences` をクリックし、フォルダとポート番号を選択して適用します。
3. **開始**: `Launch Server` をクリックすると、ブラウザが開きローカルサーバーが起動します。
4. **停止**: `Stop Server` をクリックしてローカルサーバーを停止します。

## 初回起動時の実行許可方法
未署名のアプリであるため、OSの保護機能が表示される場合があります。

### Windows
1. 「Windowsによって PC が保護されました」と表示されたら **「詳細情報」** をクリック。
2. **「実行」** ボタンを押すと起動します。

### macOS
1. ファイルを右クリック（またはControl＋クリック）して **「開く」** を選択。
2. 確認ダイアログが表示されるので、再度 **「開く」** をクリック。

## Python環境
Python環境で実行する場合。

**実行方法:**
```bash
pip install customtkinter
python InstantSava.py
```
