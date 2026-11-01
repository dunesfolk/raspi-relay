# raspi-relay

初代 Raspberry Pi（Raspberry Pi 1）とリレーモジュールを使い、Windows から
コマンド 1 行で **回路を約 1 秒だけ切断する** ための装置です。

```
Windows PC                        Raspberry Pi 1                  リレー            対象の回路
curl -X POST                ──▶   HTTP サーバー (8080番)  ──GPIO──▶  COM ─┐
http://{raspi_ip}:8080/pulse      リレーを1秒だけON                  NC ─┴── 普段はつながっている
                                                                         ON の間だけ切れる
```

- 回路はリレーの **NC（ノーマルクローズ）** 側に接続します。リレーが OFF のとき回路はつながっています。
  （設定で **NO（ノーマルオープン）** 側への接続にも切り替えられます → [4-4](#4-4-no-側に接続する場合)）
- `/pulse` を受け取ると、回路を設定した秒数（初期値 1 秒）だけ切断し、その後元に戻します。
- 切断中に `/rearm` を送ると、秒数の途中でもすぐに回路を元に戻します。
- SD カードを **読み取り専用** にして RAM 上で動かすため、突然電源を抜いても SD カードが壊れにくくなります。
- Raspberry Pi が停止したり電源が切れたりした場合も、リレーは OFF のままなので **回路はつながったまま** になります。

---

## 目次

1. [必要なもの](#1-必要なもの)
2. [SD カードに OS を書き込む](#2-sd-カードに-os-を書き込む)
3. [Windows から SSH で接続する](#3-windows-から-ssh-で接続する)
4. [リレーの配線](#4-リレーの配線)
5. [ソフトウェアのインストール](#5-ソフトウェアのインストール)
6. [設定ファイル（IP アドレスなど）](#6-設定ファイルip-アドレスなど)
7. [動作確認](#7-動作確認)
8. [SD カードを読み取り専用にする（RAM で動かす）](#8-sd-カードを読み取り専用にするram-で動かす)
9. [設定を変更したいとき・メンテナンス](#9-設定を変更したいときメンテナンス)
10. [トラブルシューティング](#10-トラブルシューティング)
11. [API・ファイル構成](#11-apiファイル構成)

---

## 1. 必要なもの

| もの | 説明 |
|---|---|
| Raspberry Pi 1 **Model B / B+** | LAN ポートが必要なので Model A / A+ は使えません |
| microSD カード（B+）/ SD カード（B） | 8GB 以上 |
| 電源 | micro USB、5V 1A 以上 |
| LAN ケーブル | ルーターやスイッチにつなぎます |
| リレーモジュール | 5V 1 回路、フォトカプラ絶縁、H/L 切替ジャンパ付き（[Amazon](https://www.amazon.co.jp/dp/B0HDSKS1J8)） |
| ジャンパーワイヤー（メス-メス）3 本 | Raspberry Pi とリレーをつなぎます |
| Windows PC | Windows 10 以降（`curl` と `ssh` が最初から入っています） |
| SD カードリーダー | OS の書き込みと設定ファイルの編集に使います |

---

## 2. SD カードに OS を書き込む

1. Windows PC に **Raspberry Pi Imager** をインストールします。
   https://www.raspberrypi.com/software/
2. Imager を起動し、次のように選びます。
   - **デバイス**: 「Raspberry Pi 1」（一覧にない場合は「No filtering / フィルタリングしない」）
   - **OS**: 「Raspberry Pi OS (other)」→ **「Raspberry Pi OS Lite (32-bit)」**
     - 初代 Raspberry Pi で動くのは **32-bit 版だけ** です。64-bit 版は起動しません。
     - 画面なしで使うので **Lite**（デスクトップなし）を選びます。
   - **ストレージ**: SD カード
3. 「次へ」→「設定を編集する」で以下を入力します。
   - **ホスト名**: `raspi-relay`
   - **ユーザー名 / パスワード**: 好きなもの（例: ユーザー名 `pi`）。忘れないようにメモしてください。
   - **ロケール**: タイムゾーン `Asia/Tokyo`、キーボード `jp`
   - **サービス** タブ: **「SSH を有効にする」** にチェックし、「パスワード認証を使う」を選択
4. 「はい」で書き込みます。終わったら SD カードを Raspberry Pi に差し込みます。
5. LAN ケーブルをつないでから電源を入れます。
   - 初代 Raspberry Pi は遅いので、**初回起動には 5〜10 分ほどかかります**。緑の LED の点滅が落ち着くまで待ちましょう。

---

## 3. Windows から SSH で接続する

Windows で「ターミナル」または「コマンドプロンプト」を開き、次を入力します
（`pi` は手順 2 で決めたユーザー名に置き換えてください）。

```cmd
ssh pi@raspi-relay.local
```

- 初回は `Are you sure you want to continue connecting?` と聞かれるので `yes` と入力します。
- パスワードを入力します（入力しても画面には何も表示されませんが、正常です）。
- `pi@raspi-relay:~ $` と表示されれば接続成功です。

> **`raspi-relay.local` で接続できない場合**
> ルーターの管理画面で「raspi-relay」に割り当てられた IP アドレスを確認し、
> `ssh pi@192.168.1.xx` のように IP アドレスで接続してください。

以降、`$` から始まるコマンドは、この SSH 画面に入力します（`$` 自体は入力しません）。

---

## 4. リレーの配線

> ⚠ **配線は必ず Raspberry Pi の電源を抜いた状態で行ってください。**
> ⚠ リレーの接点側（COM / NC）に **AC100V などの商用電源をつなぐ場合は、電気工事士などの有資格者が作業してください**。

### 4-1. リレーのジャンパを「H」にする

リレー基板のジャンパピンを **H（ハイレベルトリガ）** 側に差してください。

**理由**: Raspberry Pi の起動中や停止中は GPIO が LOW になります。H にしておくと、
その間リレーは OFF のままになり、回路は **切れません**。
L にすると、起動のたびに回路が切れてしまいます。

### 4-2. Raspberry Pi とリレーをつなぐ

Raspberry Pi の GPIO ピンは、基板の角（SD カードと反対側）にある 2 列のピンです。
ピン番号は下の図のとおりです（**1 番ピンは基板上の四角いハンダ跡のピン**）。

```
                 Raspberry Pi 1 GPIO ヘッダー（上から見た図・一部）

                   ┌──────────────┐
          3.3V   1 │ ●          ● │ 2   5V      ◀── リレー DC+
                 3 │ ●          ● │ 4   5V
                 5 │ ●          ● │ 6   GND     ◀── リレー DC-
                 7 │ ●          ● │ 8
                 9 │ ●          ● │ 10
  リレー IN ──▶ 11 │ ●          ● │ 12
     (GPIO17)      │  ...    ...  │
                   └──────────────┘
```

| リレー側の端子 | Raspberry Pi 側 | 線の色の例 |
|---|---|---|
| **DC+**（VCC） | **2 番ピン**（5V） | 赤 |
| **DC-**（GND） | **6 番ピン**（GND） | 黒 |
| **IN** | **11 番ピン**（GPIO17） | 黄 |

Model B（26 ピン）でも Model B+（40 ピン）でも、ピン番号は同じです。

### 4-3. リレーと対象の回路をつなぐ

リレーの反対側にあるネジ端子に、切断したい回路の線をつなぎます。

```
      対象の回路の線を途中で切って、
      片方を COM、もう片方を NC につなぐ

   ───────┐               ┌───────
          │   ┌───────┐   │
          └── │ COM   │   │
              │ NC    │ ──┘
              │ NO    │  （NO は使いません）
              └───────┘
```

| 端子 | 意味 | 使い方 |
|---|---|---|
| **COM** | 共通 | 回路の片側 |
| **NC** | ノーマルクローズ（普段つながっている） | 回路のもう片側 |
| NO | ノーマルオープン（普段は切れている） | **使いません** |

### 4-4. NO 側に接続する場合

NC ではなく **COM と NO** に回路をつなぐこともできます。その場合は設定ファイルで
`contact = no` にします（[手順 6](#6-設定ファイルip-アドレスなど)）。

| | `contact = nc`（推奨） | `contact = no` |
|---|---|---|
| 回路をつなぐ端子 | COM と **NC** | COM と **NO** |
| 普段のリレー | OFF（回路はつながっている） | **ON**（回路はつながっている） |
| `/pulse` を受けたとき | 指定秒数だけ ON → 回路が切れる | 指定秒数だけ OFF → 回路が切れる |
| Raspberry Pi の電源が切れている・起動中・停止したとき | 回路は **つながったまま** | 回路は **切れる** |

> ⚠ `contact = no` では、停電や起動中（初代 Pi では 1〜2 分）に **回路が切れた状態** になります。
> 回路が切れると困る用途では、`contact = nc` を使ってください。

---

## 5. ソフトウェアのインストール

SSH で接続した画面で、以下を 1 行ずつ入力します。

```bash
$ sudo apt update
$ sudo apt install -y git
$ git clone https://github.com/<ユーザー名>/raspi-relay.git
$ cd raspi-relay
$ sudo ./scripts/install.sh
```

- `<ユーザー名>` は、このリポジトリを置いている GitHub のユーザー名に置き換えてください。
- 初代 Raspberry Pi では **インストールに 10〜20 分ほどかかる** ことがあります。
- 最後に `Done.` と表示されれば完了です。

インストールスクリプトは次のことをします。

- 必要なパッケージ（`python3`, `python3-gpiozero`）をインストール
- プログラムを `/opt/raspi-relay/` にコピー
- 設定ファイル `/boot/firmware/raspi-relay.conf` を作成（すでにあれば残します）
- 起動時に自動で動くサービスを登録
- ログを RAM だけに保存する設定（SD カードへの書き込みを減らす）

必要なら次の手順 6 で設定を変更し、その後再起動します。

```bash
$ sudo reboot
```

---

## 6. 設定ファイル（IP アドレスなど）

設定ファイルは **`/boot/firmware/raspi-relay.conf`** です。起動するたびに読み込まれます。

### 編集方法 A: Raspberry Pi 上で編集する

```bash
$ sudo nano /boot/firmware/raspi-relay.conf
```

編集したら `Ctrl + O` → `Enter` で保存し、`Ctrl + X` で終了します。その後 `sudo reboot` で再起動します。

### 編集方法 B: Windows で SD カードを直接編集する

1. Raspberry Pi の電源を抜き、SD カードを PC のカードリーダーに差します。
2. **「bootfs」** という名前のドライブが表示されるので、その中の `raspi-relay.conf` をメモ帳で開きます。
3. 編集して保存し、SD カードを Raspberry Pi に戻して電源を入れます。

> 「ドライブをフォーマットしますか？」と聞かれても **フォーマットしないでください**（Linux 用の領域が見えているだけです）。

この方法なら、手順 8 で読み取り専用にした後でも設定を変更できます。

### 設定例

**例 1: IPv4 も IPv6 も自動（DHCP）** ※初期設定

```ini
[network]
interface = eth0
ipv4_method = dhcp
ipv6_method = auto
```

**例 2: IPv4 を固定 IP にする**

```ini
[network]
interface = eth0
ipv4_method = static
ipv4_address = 192.168.1.50/24
ipv4_gateway = 192.168.1.1
ipv4_dns = 192.168.1.1
ipv6_method = auto
```

- `/24` はサブネットマスク `255.255.255.0` のことです。
- 他の機器と重ならない IP アドレスを選んでください（ネットワーク管理者に確認してください）。

**例 3: IPv6 も固定にする / IPv6 を使わない**

```ini
ipv6_method = static
ipv6_address = fd00::50/64
ipv6_gateway = fd00::1
ipv6_dns =
```

```ini
ipv6_method = disabled
```

### 設定項目一覧

| セクション | 項目 | 値 | 説明 |
|---|---|---|---|
| `[network]` | `interface` | `eth0` | LAN の名前（初代 Pi は `eth0`） |
| | `ipv4_method` | `dhcp` / `static` | IPv4 を自動にするか固定にするか |
| | `ipv4_address` | `192.168.1.50/24` | 固定 IP（`static` のときだけ使用） |
| | `ipv4_gateway` | `192.168.1.1` | デフォルトゲートウェイ |
| | `ipv4_dns` | `192.168.1.1` | DNS（カンマ区切りで複数可） |
| | `ipv6_method` | `auto` / `static` / `disabled` | IPv6 の設定方法 |
| | `ipv6_address` | `fd00::50/64` | 固定 IPv6（`static` のときだけ使用） |
| | `ipv6_gateway`, `ipv6_dns` | | 省略可 |
| `[relay]` | `gpio_pin` | `17` | リレー IN をつないだ GPIO 番号 |
| | `active_high` | `true` / `false` | ジャンパ H なら `true`、L なら `false` |
| | `contact` | `nc` / `no` | 回路をつないだ端子（[4-4](#4-4-no-側に接続する場合)） |
| | `break_seconds` | `1.0` | `/pulse` で回路を切断する秒数（0.05〜3600、小数も可）。途中で `/rearm` を送ると早く戻せます |
| `[server]` | `port` | `8080` | 待ち受けポート番号 |
| | `bind` | `::` | `::` で IPv4 / IPv6 の両方で待ち受け |

> 設定の書き間違い（IP アドレスの形式が正しくないなど）があった場合は、
> 接続できなくなるのを防ぐため **自動的に DHCP で起動** します。

---

## 7. 動作確認

### Raspberry Pi 上で確認

```bash
$ systemctl status raspi-relay
```

`active (running)` と表示されていれば動いています（`q` で終了）。

現在の IP アドレスを確認するには:

```bash
$ ip addr show eth0
```

`inet 192.168.1.50/24` のように表示されるのが IPv4 アドレス、`inet6` が IPv6 アドレスです。

### Windows から回路を切断する

コマンドプロンプトで次を入力します（`192.168.1.50` は Raspberry Pi の IP アドレスに置き換えます）。

```cmd
curl -X POST http://192.168.1.50:8080/pulse
```

- リレーが「カチッ」と鳴り、約 1 秒後にもう一度「カチッ」と鳴れば成功です。
- 画面に `{"result": "ok", "break_seconds": 1.0}` と表示されます（切断が **始まった時点** ですぐに返ります）。

### 切断を途中でやめる（rearm）

`break_seconds` を長く（例: 60 秒）設定している場合、切断中に次を送ると、すぐに回路が元に戻ります。

```cmd
curl -X POST http://192.168.1.50:8080/rearm
```

- 切断中だった場合は `{"result": "rearmed"}` と表示されます。
- 切断中でなかった場合は `{"result": "idle"}` と表示されます（何も変わりません）。

リポジトリの `client\pulse.cmd` も使えます。

```cmd
pulse.cmd 192.168.1.50
rearm.cmd 192.168.1.50
```

IPv6 で接続する場合は、アドレスを `[ ]` で囲みます。

```cmd
curl -X POST http://[fd00::50]:8080/pulse
```

### ログを見る

```bash
$ journalctl -u raspi-relay -f
```

`Ctrl + C` で終了します。

---

## 8. SD カードを読み取り専用にする（RAM で動かす）

すべての動作確認が終わったら、SD カードを読み取り専用にします。

**仕組み**: Raspberry Pi OS の「オーバーレイファイルシステム」機能を使います。
SD カードは読み取り専用になり、動作中の変更はすべて RAM 上に保存されます。
そのため、**突然電源が切れても SD カードの中身が壊れにくくなります**。
（RAM 上の変更は再起動すると消えます。）

### 手順

```bash
$ sudo raspi-config
```

1. 矢印キーで **「4 Performance Options」** を選んで `Enter`
2. **「P2 Overlay File System」** を選んで `Enter`
3. 「Would you like the overlay file system to be enabled?」→ **「はい / Yes」**
4. 「Would you like the boot partition to be write-protected?」→ **「はい / Yes」**
5. 「OK」→ `Finish` →「再起動しますか？」→ **「はい / Yes」**

> メニューの番号や表記は OS のバージョンによって少し異なることがあります。

コマンドで設定する場合は次のとおりです。

```bash
$ sudo raspi-config nonint enable_overlayfs
$ sudo raspi-config nonint enable_bootro
$ sudo reboot
```

### 読み取り専用になったか確認する

再起動後、SSH で接続して次を入力します。

```bash
$ findmnt /
$ findmnt /boot/firmware
```

- `/` の行に **`overlay`** と表示されていれば、RAM で動いています。
- `/boot/firmware` の行に **`ro`** と表示されていれば、ブート領域も読み取り専用です。

これで完成です。あとは電源を入れるだけで自動的に動きます。

---

## 9. 設定を変更したいとき・メンテナンス

### IP アドレスなどの設定だけ変えたい

いちばん簡単なのは、[手順 6 の編集方法 B](#編集方法-b-windows-で-sd-カードを直接編集する)
（Windows で SD カードを直接編集）です。

Raspberry Pi 上で編集する場合は、ブート領域を一時的に書き込み可能にします。

```bash
$ sudo mount -o remount,rw /boot/firmware
$ sudo nano /boot/firmware/raspi-relay.conf
$ sudo mount -o remount,ro /boot/firmware
$ sudo reboot
```

### OS の更新やソフトウェアの再インストールをしたい

読み取り専用のままだと、変更は再起動で消えてしまいます。いったん解除します。

1. `sudo raspi-config` →「4 Performance Options」→「P2 Overlay File System」
   - オーバーレイ → **「いいえ / No」**
   - ブート領域の書き込み保護 → **「いいえ / No」**
2. 再起動します（`sudo reboot`）。
3. 作業をします（例: `sudo apt update && sudo apt full-upgrade -y`）。
   ソフトウェアを更新する場合は次のとおりです。
   ```bash
   $ cd ~/raspi-relay
   $ git pull
   $ sudo ./scripts/install.sh
   ```
4. 終わったら [手順 8](#8-sd-カードを読み取り専用にするram-で動かす) で再び読み取り専用にします。

### アンインストール

```bash
$ cd ~/raspi-relay
$ sudo ./scripts/uninstall.sh
```

---

## 10. トラブルシューティング

| 症状 | 確認すること |
|---|---|
| `curl` で接続できない | IP アドレスは正しいか（`ip addr show eth0`）。PC と同じネットワークにいるか。`systemctl status raspi-relay` が `active (running)` か |
| `{"result": "busy"}` と返る | 前のパルスが動作中です。1 秒以上空けて再度送ってください |
| リレーが鳴らない | 配線（2 番・6 番・11 番ピン）を確認。ジャンパが H で、設定が `active_high = true` か |
| 起動のたびに回路が切れる | ジャンパが **L** になっていませんか？ **H** に変更し、`active_high = true` にしてください。`contact = no` の場合は、起動中に回路が切れるのは仕様です（[4-4](#4-4-no-側に接続する場合)） |
| 普段から回路が切れていて、`/pulse` でつながる | 配線と `contact` の設定が合っていません。NC につないだなら `contact = nc`、NO につないだなら `contact = no` にしてください |
| リレーの LED は点くが「カチッ」と鳴らない | 電源が足りない可能性があります。5V 1A 以上の電源を使ってください |
| 固定 IP にしたら接続できなくなった | 設定ミスの可能性があります。[手順 6 の編集方法 B](#編集方法-b-windows-で-sd-カードを直接編集する) で `ipv4_method = dhcp` に戻してください |
| 設定を変えたのに反映されない | 設定は **起動時** に読み込まれます。`sudo reboot` してください |
| インストールで `overlay file system is ON` と出る | 読み取り専用のままです。[手順 9](#os-の更新やソフトウェアの再インストールをしたい) で解除してください |
| ネットワーク設定のログを見たい | `journalctl -u raspi-relay-network` |

---

## 11. API・ファイル構成

### API

| メソッド | パス | 動作 | 応答 |
|---|---|---|---|
| `POST` | `/pulse` | 回路を `break_seconds` 秒だけ切断してから元に戻す | `200 {"result": "ok", "break_seconds": 1.0}`（切断開始時にすぐ返ります） / 切断中なら `409 {"result": "busy"}` |
| `POST` | `/rearm` | 切断中なら、すぐに回路を元に戻す | 切断中だった: `200 {"result": "rearmed"}` / 切断中でなかった: `200 {"result": "idle"}` |
| `GET` | `/health` | 動作確認 | `200 {"result": "ok"}` |

### ファイル構成

```
raspi-relay/
├── README.md                         このファイル
├── config/raspi-relay.conf           設定ファイルのひな形
├── src/raspi_relay/
│   ├── server.py                     HTTP サーバーとリレー制御
│   ├── apply_network.py              起動時に IP アドレスを設定（nmcli を使用）
│   └── config.py                     設定ファイルの読み込み
├── systemd/
│   ├── raspi-relay-network.service   起動時にネットワーク設定を適用
│   └── raspi-relay.service           HTTP サーバーのサービス（停止しても自動で再起動）
├── scripts/
│   ├── install.sh                    インストール
│   └── uninstall.sh                  アンインストール
└── client/
    ├── pulse.cmd                     Windows 用: 回路を切断する
    └── rearm.cmd                     Windows 用: 切断を途中でやめる
```

### PC でのテスト（開発者向け）

GPIO を使わずに PC 上でサーバーを試せます。

```bash
cd src/raspi_relay
python server.py --fake-gpio --config ../../config/raspi-relay.conf
python apply_network.py --dry-run --config ../../config/raspi-relay.conf
```

## ライセンス

MIT
