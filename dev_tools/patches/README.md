# 本地 hamlib 补丁 / 上游改进清单（IC-M710 / icmarine 家族）

背景：MRRC（radio1）用 IC-M710 + rigctld，第三方日志软件（RUMlogNG）轮询同一个 rigctld。
2026-10-04 在**真机**上把协议、后端源码（4.7.2 与最新 master）逐项对照后，确认了下列问题，
每个都做成了可单独提交的补丁（对最新 master `7a556db` `git apply -p1` 干净应用、`make` 通过）。

## 实测到的协议事实（探针脚本思路见下）

- 物理层 RS-232 4800，现场工作配置 **8N2**（caps 里写的是 8N1，见下）。
- 帧格式（NMEA-0183 风格专有句，XOR 校验，CR LF 结尾）：
  `$PICOA,90,<remote_id>,<CMD>[,<param>]*XX`；应答是**原样回显**发送的句子。
- **本机不回答任何查询**：对 `SIGM/SQLS/RXF/AFG/RFG/AGC/TXP/MODE/NB/TUNER` 十条只读查询，
  回包全部只是原句回显、不带数值 → hamlib 头文件那句 "The M710 does not support queries"
  属实，"虚拟副本"（`priv->rxfreq/mode/...`）是必要设计。
- 写命令靠回显比对确认（`icmarine_transaction` 的 memcmp）；这就是 PTT（`TRX,TX/RX`）、
  频率（`RXF/RXF`）、模式（`MODE,USB,2200`）等能正常工作的原因。

## 补丁（按建议的提交顺序）

### ① `icm710-mode-cache.patch`（bug）

`icm710_set_mode()` 从不写 `priv->mode`（只有 `set_freq()` 写了 `rxfreq`）→ `get_mode()`
只能在 hamlib 的 get 缓存（实测 ∼1.0 s）内可读，之后恒为 `RIG_MODE_NONE`。现象：轮询
rigctld 的日志软件永远读不到模式。修法：与 `set_freq()` 完全对称，**成功后才**记。

### ② `icm710-agc-copy.patch`（bug）

`icm710_set_level()` 的 `case RIG_LEVEL_AGC` 把值存进了 **`priv->afgain`** → 设 AGC 污染
AF 增益副本，而 `get_level(AGC)` 永远返回 0（没人写 `priv->agc`）。修法：改成 `priv->agc`。

### ③ `icm710-caps-honesty.patch`（caps 谎报）

- `ICM710_LEVEL_ALL` 里的 `RIG_LEVEL_RAWSTR`：本机永远读不到（SIGM 只回显）——**客户端会
  无限轮询一个死电平**（MRRC 实测：每 0.5 s 一次失败 + 刷满 rigctld 日志）。删掉声明。
- `.dcd_type = RIG_DCD_RIG` → `RIG_DCD_NONE`（SQLS 无响应；700pro/802/803 能答，保留它们的）。
- `.has_get_func = ICM710_FUNC_ALL`（NB）→ `RIG_FUNC_NONE`：NB 是只写命令，且结构体里
  没有存储字段 → `get_func(NB)` 实际是把回显拿去 `strcmp("ON")`，恒报 off。

## 建议（尚未做补丁，需要维护者拍板）

1. `icmarine_transaction()` 对"查询"的判定应该更硬：响应 == 发送句（无参数）时应返回
   `-RIG_ENAVAIL`/`-RIG_EPROTO`，而不是把回显当值解析 —— 这正是 `get_func(NB)` 静默错报的机制。
2. 家族四个后端（`icm700pro/icm710/icm802/icm803`）**都不记 mode** —— 同一修法应该四份都打。
3. 四个后端都注册了 `str_cal`，但**无人实现 `get_smeter`**（M710 不可能；700pro/802/803 靠
   `get_level(RAWSTR)` + `str_cal` 可以工作）。建议 M710 去掉 `str_cal`，其余保留并补测试。
4. `tests/rigctl_parse.c` 的 caps dump 把 `PTT type` 打印成 **PTT 端口类型**（`PTTPORT(rig)->type.ptt`）
   而不是 `caps->ptt_type` —— M710 明明声明了 `RIG_PTT_RIG`，dump 却显示 `None`，排查
   "不能发射"时会被误导。建议两者分开打印。
5. caps 写 `serial_stop_bits = 1`（dump 显示 8N1），而现场长期稳定工作是 8N2 —— 建议按
   手册核对后统一（至少加注释）。

## 构建/安装（站内，独立前缀，不动 MacPorts）

```bash
tar xzf /opt/local/var/macports/distfiles/hamlib/hamlib-4.7.2.tar.gz -C /tmp
cd /tmp/hamlib-4.7.2
for p in icm710-mode-cache icm710-agc-copy icm710-caps-honesty; do
  patch -p1 < <repo>/dev_tools/patches/$p.patch
done
./configure --prefix=/usr/local/mrrc-hamlib --disable-static --without-cxx-binding \
    --without-perl-binding --without-python-binding --without-tcl-binding
make -j6 && sudo make install
```

（站内目前只装了 ①；②③ 属于行为/caps 变更，建议随上游一起动再升级。）

实例配置里指认（`mrrc_multi.sh` 会读；空 = 用 PATH 里的 rigctld）：

```ini
[HAMLIB]
rigctld_bin = /usr/local/mrrc-hamlib/bin/rigctld
```

## 验证

```bash
printf 'M LSB 2200\n' | nc 127.0.0.1 4531     # RPRT 0
sleep 16
printf 'm\n' | nc 127.0.0.1 4531              # 补丁①：LSB 2200；原版：空模式 + 2200
printf 'f\n' | nc 127.0.0.1 4531              # 7050000（应用侧 F11 恢复过虚拟状态）
```

## 上游源码（对照用）

- 克隆位置：`~/HAM/ref/Hamlib`（`git clone https://github.com/Hamlib/Hamlib.git --depth 1`），
  2026-10-04 对照时 master = `7a556db`（2026-10-03）。
- 4.7.2 → master 该后端只差一行 `#include "hamlib/rig_state.h"`；上述问题全在 master 仍然存在。
- 三个补丁对 master 干净应用且 `make` 通过（实测）。

**上游**：这两处（`set_mode` 不记模式、`RAWSTR` 声明未实现）都值得开 GitHub issue。

## 上游源码（对照用）与现状

- 克隆位置：`~/HAM/ref/Hamlib`（`git clone https://github.com/Hamlib/Hamlib.git --depth 1`），
  2026-10-04 对照时 master = `7a556db`（2026-10-03）。
- **对照结论：两个 bug 在最新 master 依然存在** —— `priv->mode` 在该文件里出现 0 次；
  `get_level()` 仍只实现 AF/RF/RFPOWER/AGC，而 `ICM710_LEVEL_ALL` 掩码里照旧声明
  `RIG_LEVEL_RAWSTR`。同族四个后端（`icm700pro/icm710/icm802/icm803`）**都是这个模式**。
- 本补丁 `git apply -p1` 可**干净应用到 master**（只动一个文件）。要提交上游时直接用
  这个文件；若要顺手把 RAWSTR 的假声明也修掉（从 `ICM710_LEVEL_ALL` 去掉
  `RIG_LEVEL_RAWSTR`，因为该机不响应查询 → 永远读不到 S 表），属于同一类修复。

**构建/安装**（独立前缀，不动 MacPorts；构建机需要 Xcode CLT）：

```bash
# 站内运行用稳定发行版 + 补丁（下面以 4.7.2 tarball 为例；MacPorts 的 distfiles 里有）
tar xzf /opt/local/var/macports/distfiles/hamlib/hamlib-4.7.2.tar.gz -C /tmp
cd /tmp/hamlib-4.7.2
patch -p1 < <repo>/dev_tools/patches/icm710-mode-cache.patch
./configure --prefix=/usr/local/mrrc-hamlib --disable-static --without-cxx-binding \
    --without-perl-binding --without-python-binding --without-tcl-binding
make -j6 && sudo make install
```

（用上游克隆构建同样可行：先 `./bootstrap` 生成 configure 再同上。）
