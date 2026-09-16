#!/bin/bash

# MRRC 性能与健康监控脚本
#
# M18 (2026-09-15): 重写。修复 7 处 macOS 失效检测 + 新增可复现本次分析的指标。
#   修复：
#     1. ps 的 --no-headers 是 GNU 选项，macOS 上直接报错 → 所有 ps 调用返回空
#        （basic 看不到进程信息、realtime 显示 "CPU: %"）。改用 BSD 的 -o fmt=。
#     2. 内存换算硬编码 4096 字节页；Apple Silicon 为 16384 → 少算 4 倍。
#        现从 vm_stat 首行动态取页大小。
#     3. "CPU 使用率" 实为 awk '{print $3}' = user% 单项，不是总占用。现报 user+sys。
#     4. realtime 硬编码端口 8899（M17 只修了 WEB_PORT）→ 现统一从配置解析。
#     5. rigctld 硬编码 4532，radio1 实为 4531 → 现读 INSTANCE_SETTINGS.instance_rigctl_port。
#     6. 日志文件名（mrrc_service.log/mrrc_debug.log/mrrc.log）在本机不存在 →
#        现按 mrrc_multi.sh 约定解析 mrrc_<name>.log / rigctld_<name>.log / atr1000_<name>.log。
#     7. pgrep -f "MRRC" 多实例下返回多 PID、[ "$X" -gt 50 ] 空值报错 → 现按实例匹配 + 整数兜底。
#   新增：
#     cpu [秒]  每线程 CPU 内核记账（ps -M 累计 utime/stime 差分）——macOS 上唯一可信的
#               线程级归因法；py-spy 的线程百分比在此平台是伪值（每线程等分样本）。
#     mem       进程 footprint（含 peak，用于查内存泄漏）+ 系统内存压力等级 / swap /
#               pagein-pageout 速率（交换抖动检测）。
#     health    从日志提取 IOLoop watchdog / 🚨 stall / TX 初始化 p.open 耗时 / ATR 数据新鲜度。
#     退出码    status/health/mem：0 正常，1 警告，2 严重（可直接用于 cron/launchd 告警）。
#   注意：status 不再枚举音频设备。枚举会打开 CoreAudio，蓝牙音频设备在场时可触发 A2DP
#   抖动并拖慢全局 CoreAudio（见 docs/current/reliability/RC-001 §7）；需要时显式跑 audio。
#
# 本地监控；远程用法：ssh <host> "/path/to/mrrc_monitor.sh status"
#
# 用法: ./mrrc_monitor.sh [选项] [命令]
#   -i, --instance <name>  目标实例（main = MRRC.conf；radio1 = MRRC.radio1.conf）
#   -a, --all              所有已配置实例（默认：自动探测，多实例运行时逐个报告）
#   -n, --interval <sec>   采样间隔：cpu 采样窗口 / realtime 刷新周期（默认 cpu 10s、realtime 5s）
#   MRRC_INSTANCE          环境变量，等价于 -i

# Get the directory where this script is located
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
MRRC_DIR="$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 判定计数（供 status/health 汇总与退出码使用）
WARN_COUNT=0
CRIT_COUNT=0

# 日志函数
log_info() {
	echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
	echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
	WARN_COUNT=$((WARN_COUNT + 1))
	echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
	CRIT_COUNT=$((CRIT_COUNT + 1))
	echo -e "${RED}✗ $1${NC}"
}

# 仅打印，不计入判定（用于"这一项本来就允许为空"的场景）
log_note() {
	echo -e "${CYAN}ℹ${NC} $1"
}

###############################################################################
# 实例解析（约定与 mrrc_multi.sh 保持一致）
###############################################################################

# 列出已配置实例名（main = 无后缀配置）
list_instances() {
	local found=""
	[ -f "$SCRIPT_DIR/MRRC.conf" ] && found="main"
	local name
	for conf in "$SCRIPT_DIR"/MRRC.*.conf; do
		[ -f "$conf" ] || continue
		name=$(basename "$conf")
		name=${name#MRRC.}
		name=${name%.conf}
		# 与 mrrc_multi.sh 相同的排除规则（备份/历史实例）
		case "$name" in
		bak | *bak | *orig | 9000 | *~) continue ;;
		esac
		found="$found $name"
	done
	echo "$found" | tr ' ' '\n' | grep -v '^$'
}

# 该实例的进程匹配模式（pgrep -f）
instance_pattern() {
	if [ "$1" = "main" ]; then
		echo 'MRRC(\.conf)?$'
	else
		echo "MRRC\\.$1\\.conf"
	fi
}

# 由 pid 文件或 pgrep 解析 MRRC 主进程 PID
resolve_mrrc_pid() {
	local inst="$1" pidfile pid
	# 主实例不写 pid 文件（mrrc_multi.sh 只管命名实例）→ 直接用 pgrep 模式匹配
	if [ "$inst" = "main" ]; then
		pgrep -f "$(instance_pattern main)" 2>/dev/null | head -1
		return 0
	fi
	pidfile="$MRRC_DIR/mrrc_${inst}.pid"
	if [ -f "$pidfile" ]; then
		pid=$(tr -dc '0-9' <"$pidfile")
		# pid 文件可能过期（PID 复用）→ 校验命令行确实属于本实例
		if [ -n "$pid" ] && ps -p "$pid" -o command= 2>/dev/null | grep -q "MRRC\.${inst}\.conf"; then
			echo "$pid"
			return 0
		fi
	fi
	pgrep -f "$(instance_pattern "$inst")" 2>/dev/null | head -1
}

# 由 pid 文件或 pgrep 解析伴生进程 PID（rigctld / atr1000_proxy）
resolve_companion_pid() {
	local inst="$1" kind="$2" pidfile pid
	if [ "$inst" = "main" ]; then
		pidfile="$MRRC_DIR/${kind}.pid"
	else
		pidfile="$MRRC_DIR/${kind}_${inst}.pid"
	fi
	if [ -f "$pidfile" ]; then
		pid=$(tr -dc '0-9' <"$pidfile")
		[ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1 && {
			echo "$pid"
			return 0
		}
	fi
	case "$kind" in
	# V5.8.6: 用本实例的 socket 路径限定代理，避免另一部署的代理被误认
	rigctld) pid=$(pgrep -f "rigctld.*-t ${RIG_PORT:-4532}" 2>/dev/null | head -1) ;;
	atr1000) pid=$(pgrep -f "atr1000_proxy.*$(basename "$UNIX_SOCKET")" 2>/dev/null | head -1) ;;
	esac
	[ -n "$pid" ] && echo "$pid"
}

# 读取实例配置（python3 优先，grep 兜底）。结果以 KEY=VALUE 行输出。
_conf_read() {
	local conf="$1" inst="$2"
	if [ ! -f "$conf" ]; then
		echo "CONF_MISSING=1"
		return 0
	fi
	python3 - "$conf" "$inst" <<'PYEOF' 2>/dev/null
import sys, configparser
conf, inst = sys.argv[1], sys.argv[2]
c = configparser.ConfigParser()
try:
    c.read(conf)
except Exception:
    pass

def g(section, key, default=''):
    try:
        return c.get(section, key).strip()
    except Exception:
        return default

web = g('INSTANCE_SETTINGS', 'instance_port') or g('SERVER', 'port', '8877')
print('WEB_PORT=' + (web or '8877'))
print('RIG_HOST=' + (g('INSTANCE_SETTINGS', 'instance_rigctl_host') or '127.0.0.1'))
print('RIG_PORT=' + (g('INSTANCE_SETTINGS', 'instance_rigctl_port') or '4532'))
print('ATR_DEVICE=' + g('INSTANCE_SETTINGS', 'instance_atr1000_device'))
print('ATR_PORT=' + g('INSTANCE_SETTINGS', 'instance_atr1000_port'))
print('LOG_DIR=' + (g('INSTANCE_SETTINGS', 'instance_log_dir') or '.'))
print('UNIX_SOCKET=' + g('INSTANCE_SETTINGS', 'instance_unix_socket'))
print('SERVER_DEBUG=' + (g('SERVER', 'debug', 'False') or 'False'))
print('CTRL_DEBUG=' + (g('CTRL', 'debug', 'False') or 'False'))
PYEOF
}

# grep 兜底解析（无 python3 时）
_conf_read_fallback() {
	local conf="$1" inst="$2"
	local web rigport logdir
	web=$(grep -E '^\s*port\s*=' "$conf" 2>/dev/null | head -1 | sed -E 's/.*=\s*([0-9]+).*/\1/')
	rigport=$(grep -E '^\s*instance_rigctl_port\s*=' "$conf" 2>/dev/null | head -1 | sed -E 's/.*=\s*([0-9]+).*/\1/')
	logdir=$(grep -E '^\s*instance_log_dir\s*=' "$conf" 2>/dev/null | head -1 | sed -E 's/.*=\s*(.*)$/\1/' | tr -d '\r')
	echo "WEB_PORT=${web:-8877}"
	echo "RIG_HOST=127.0.0.1"
	echo "RIG_PORT=${rigport:-4532}"
	echo "ATR_DEVICE="
	echo "ATR_PORT="
	echo "LOG_DIR=${logdir:-.}"
	echo "UNIX_SOCKET="
	echo "SERVER_DEBUG=False"
	echo "CTRL_DEBUG=False"
}

# 载入指定实例的配置为全局变量
load_instance() {
	INSTANCE="$1"
	if [ "$INSTANCE" = "main" ]; then
		CONF="$SCRIPT_DIR/MRRC.conf"
	else
		CONF="$SCRIPT_DIR/MRRC.${INSTANCE}.conf"
	fi

	if command -v python3 >/dev/null 2>&1; then
		_conf_out=$(_conf_read "$CONF" "$INSTANCE")
	else
		_conf_out=$(_conf_read_fallback "$CONF" "$INSTANCE")
	fi
	[ -z "$_conf_out" ] && _conf_out=$(_conf_read_fallback "$CONF" "$INSTANCE")

	WEB_PORT=""
	RIG_HOST=""
	RIG_PORT=""
	ATR_DEVICE=""
	ATR_PORT=""
	LOG_DIR=""
	UNIX_SOCKET=""
	SERVER_DEBUG=""
	CTRL_DEBUG=""
	local line key val
	while IFS= read -r line; do
		key=${line%%=*}
		val=${line#*=}
		case "$key" in
		WEB_PORT) WEB_PORT="$val" ;;
		RIG_HOST) RIG_HOST="$val" ;;
		RIG_PORT) RIG_PORT="$val" ;;
		ATR_DEVICE) ATR_DEVICE="$val" ;;
		ATR_PORT) ATR_PORT="$val" ;;
		LOG_DIR) LOG_DIR="$val" ;;
		UNIX_SOCKET) UNIX_SOCKET="$val" ;;
		SERVER_DEBUG) SERVER_DEBUG="$val" ;;
		CTRL_DEBUG) CTRL_DEBUG="$val" ;;
		esac
	done <<EOF
$_conf_out
EOF

	# 数值兜底：任何非数字都会让 [ -gt ] 崩掉
	case "$WEB_PORT" in '' | *[!0-9]*) WEB_PORT=8877 ;; esac
	case "$RIG_PORT" in '' | *[!0-9]*) RIG_PORT=4532 ;; esac
	[ -z "$RIG_HOST" ] && RIG_HOST="127.0.0.1"

	# 日志目录：相对路径按 mrrc_multi.sh 规则相对脚本目录
	case "$LOG_DIR" in
	"" | .) LOG_DIR="$SCRIPT_DIR" ;;
	/*) : ;;
	*) LOG_DIR="$SCRIPT_DIR/$LOG_DIR" ;;
	esac
	[ -z "$UNIX_SOCKET" ] && UNIX_SOCKET="/tmp/mrrc_${INSTANCE}.sock"

	# 日志文件名（main 用 MRRC.log，命名实例用 mrrc_<name>.log）
	if [ "$INSTANCE" = "main" ]; then
		MRRC_LOG="$LOG_DIR/MRRC.log"
	else
		MRRC_LOG="$LOG_DIR/mrrc_${INSTANCE}.log"
	fi
	RIGCTLD_LOG="$LOG_DIR/rigctld_${INSTANCE}.log"
	ATR1000_LOG="$LOG_DIR/atr1000_${INSTANCE}.log"

	MRRC_PID=$(resolve_mrrc_pid "$INSTANCE")
	RIGCTLD_PID=$(resolve_companion_pid "$INSTANCE" rigctld)
	ATR1000_PID=$(resolve_companion_pid "$INSTANCE" atr1000)
}

###############################################################################
# 指标采集（macOS 正确姿势）
###############################################################################

# 页大小（Apple Silicon = 16384，Intel = 4096）
page_size() {
	local ps_val
	ps_val=$(vm_stat 2>/dev/null | sed -n '1s/.*page size of \([0-9][0-9]*\) bytes.*/\1/p')
	echo "${ps_val:-4096}"
}

# 取 vm_stat 某一项（$NF 兼容 "Pages occupied by compressor:" 这类多词标签）
vm_stat_val() {
	vm_stat 2>/dev/null | grep -E "^$1" | head -1 | awk '{gsub(/\./,"",$NF); print $NF}' | tr -d ' '
}

# swap，单位 MB
swap_total_mb() { sysctl -n vm.swapusage 2>/dev/null | sed -n 's/.*total = \([0-9.]*\)M.*/\1/p'; }
swap_used_mb() { sysctl -n vm.swapusage 2>/dev/null | sed -n 's/.*used = \([0-9.]*\)M.*/\1/p'; }

# 内存压力等级：1 正常 / 2 偏高 / >=4 严重
pressure_level() {
	local lvl
	lvl=$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null)
	echo "${lvl:-0}"
}

# 系统 CPU：解析 user+sys+idle（top -l 2 取第二次采样，避免首采样失真）
sys_cpu_line() {
	top -l 2 -s 1 2>/dev/null | grep "^CPU usage" | tail -1
}

# 打印系统 CPU（user+sys = 总占用；原实现只取 user%）
print_sys_cpu() {
	local line usr sys idle total
	line=$(sys_cpu_line)
	if [ -z "$line" ]; then
		echo "系统 CPU: 无法采样"
		return
	fi
	usr=$(echo "$line" | sed -n 's/.*: \([0-9.]*\)% user.*/\1/p')
	sys=$(echo "$line" | sed -n 's/.*, \([0-9.]*\)% sys.*/\1/p')
	idle=$(echo "$line" | sed -n 's/.*, \([0-9.]*\)% idle.*/\1/p')
	usr=${usr:-0}
	sys=${sys:-0}
	idle=${idle:-0}
	total=$(echo "$usr $sys" | awk '{printf "%.1f", $1 + $2}')
	echo "系统 CPU: ${total}% (user ${usr}% + sys ${sys}%), idle ${idle}%"
}

# 进程 footprint（MB）：phys_footprint / peak。RSS 只算私有驻留，
# footprint 才包含映射与压缩内存，是判断泄漏的正确口径。
# 输出: "<footprint_mb> <peak_mb>"（footprint 不可用则退回 ps RSS，peak 为空）
proc_footprint() {
	local pid="$1" out fp peak
	if [ -x /usr/bin/footprint ]; then
		out=$(/usr/bin/footprint -p "$pid" 2>/dev/null)
		fp=$(echo "$out" | awk '/phys_footprint:/ {print $2}' | head -1)
		peak=$(echo "$out" | awk '/phys_footprint_peak:/ {print $2}' | head -1)
		case "$fp" in '' | *[!0-9]*) fp="" ;; esac
		[ -n "$fp" ] && {
			echo "${fp} ${peak}"
			return
		}
	fi
	fp=$(ps -p "$pid" -o rss= 2>/dev/null | tr -d ' ')
	case "$fp" in '' | *[!0-9]*) fp=0 ;; esac
	echo "$((fp / 1024)) "
}

# ATR-1000 设备 TCP 端口可达性（ping 通 ≠ 端口通）
# nc 优先（macOS 自带，-G 为连接超时秒数），无 nc 时退回 bash 的 /dev/tcp
atr_port_open() {
	local host="$1" port="$2"
	if command -v nc >/dev/null 2>&1; then
		nc -z -G 1 "$host" "$port" >/dev/null 2>&1
		return $?
	fi
	(exec 3<>"/dev/tcp/${host}/${port}") >/dev/null 2>&1
	return $?
}

# 线程数（macOS ps 无 thcount 关键字 → 用 ps -M 行数）
proc_threads() {
	local pid="$1" n
	n=$(ps -M -p "$pid" 2>/dev/null | wc -l | tr -d ' ')
	n=${n:-1}
	echo $((n > 0 ? n - 1 : 0))
}

# 单次快照：各线程累计 CPU 时间（STIME+UTIME，秒），每行一个
thread_cpu_snapshot() {
	local pid="$1"
	ps -M -p "$pid" 2>/dev/null | awk '
        NR == 1 { next }
        {
            n = 0; a = ""; b = ""
            # 时间字段始终出现在命令行之前：前两个 mm:ss.cc / h:mm:ss.cc 即 STIME、UTIME
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^[0-9]+:[0-9]+(\.[0-9]+)?$/) {
                    n++
                    if (n == 1) a = $i
                    else if (n == 2) { b = $i; break }
                }
            }
            if (n >= 2) {
                split(a, x, ":"); split(b, y, ":")
                sa = 0; for (j = 1; j <= length(x); j++) sa = sa * 60 + x[j]
                sb = 0; for (j = 1; j <= length(y); j++) sb = sb * 60 + y[j]
                printf "%.2f\n", sa + sb
            }
        }'
}

###############################################################################
# 检查项
###############################################################################

# 检查基本状态
check_basic_status() {
	echo "=== MRRC 服务基本状态 ==="
	echo "实例: ${INSTANCE}   配置: $(basename "$CONF")"

	if [ -n "$MRRC_PID" ]; then
		local uptime cpu mem rss threads fp
		uptime=$(ps -p "$MRRC_PID" -o etime= 2>/dev/null | tr -d ' ')
		cpu=$(ps -p "$MRRC_PID" -o pcpu= 2>/dev/null | tr -d ' ')
		mem=$(ps -p "$MRRC_PID" -o pmem= 2>/dev/null | tr -d ' ')
		rss=$(ps -p "$MRRC_PID" -o rss= 2>/dev/null | tr -d ' ')
		threads=$(proc_threads "$MRRC_PID")
		fp=$(proc_footprint "$MRRC_PID" | awk '{print $1}')
		log_success "MRRC 运行中 (PID: $MRRC_PID)"
		echo "  CPU: ${cpu:-?}% (单核占比)   内存: ${mem:-?}%   RSS: $((${rss:-0} / 1024)) MB   footprint: ${fp:-?} MB   线程: ${threads}"
		echo "  运行时间: ${uptime:-?}"
	else
		log_error "MRRC 进程未运行（实例 ${INSTANCE}）"
	fi

	# 伴生进程
	if [ -n "$RIGCTLD_PID" ]; then
		log_success "rigctld 运行中 (PID: $RIGCTLD_PID, ${RIG_HOST}:${RIG_PORT})"
	else
		log_warning "rigctld 未运行 (期望端口 ${RIG_PORT})"
	fi
	if [ -n "$ATR1000_PID" ]; then
		log_success "ATR-1000 代理运行中 (PID: $ATR1000_PID)"
		if [ -S "$UNIX_SOCKET" ]; then
			echo "  Unix socket: $UNIX_SOCKET"
		else
			log_warning "ATR-1000 socket 不存在: $UNIX_SOCKET"
		fi
	else
		log_warning "ATR-1000 代理未运行"
	fi

	# 端口与客户端
	if lsof -nP -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
		local clients
		clients=$(lsof -nP -iTCP:"$WEB_PORT" -sTCP:ESTABLISHED 2>/dev/null | grep -c ESTABLISHED)
		log_success "Web 服务监听端口 $WEB_PORT (已建立客户端连接: ${clients})"
	else
		log_error "Web 服务未在端口 $WEB_PORT 监听"
	fi
	echo ""
}

# 内存压力等级 + swap 使用率（system 与 mem 共用，避免阈值/文案分叉）
check_pressure_and_swap() {
	local lvl swap_t swap_u swap_pct
	lvl=$(pressure_level)
	case "$lvl" in
	1) echo "内存压力等级: 1 (正常)" ;;
	2) log_warning "内存压力等级: 2 (偏高) —— 系统开始压缩/换出" ;;
	4 | 8) log_error "内存压力等级: ${lvl} (严重) —— 已进入 Jetsam 击杀区间" ;;
	0 | "") log_note "内存压力等级: 不可用" ;;
	*) log_warning "内存压力等级: ${lvl}" ;;
	esac

	swap_t=$(swap_total_mb)
	swap_u=$(swap_used_mb)
	swap_t=${swap_t:-0}
	swap_u=${swap_u:-0}
	swap_pct=$(echo "$swap_u $swap_t" | awk '{ if ($2 > 0) printf "%d", $1 / $2 * 100; else print 0 }')
	echo "Swap: ${swap_u}MB / ${swap_t}MB (${swap_pct}%)"
	if [ "${swap_pct:-0}" -ge 90 ]; then
		log_error "Swap 使用率 ${swap_pct}% —— 换页延迟会直接打崩实时音频与 PTT 时序"
	elif [ "${swap_pct:-0}" -ge 60 ]; then
		log_warning "Swap 使用率 ${swap_pct}%"
	fi
}

# 检查系统资源
check_system_resources() {
	echo "=== 系统资源使用情况 ==="

	print_sys_cpu
	echo "负载均值:$(sysctl -n vm.loadavg 2>/dev/null | tr -d '{}' | tr -s ' ')"

	local psize total_mb free_mb active_mb wired_mb comp_mb used_mb pct
	psize=$(page_size)
	total_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
	free_mb=$(($(vm_stat_val "Pages free") * psize / 1024 / 1024))
	active_mb=$(($(vm_stat_val "Pages active") * psize / 1024 / 1024))
	wired_mb=$(($(vm_stat_val "Pages wired down") * psize / 1024 / 1024))
	comp_mb=$(($(vm_stat_val "Pages occupied by compressor") * psize / 1024 / 1024))
	# 已用 = 总 - 空闲（含压缩器占用，与活动监视器的"内存压力"观感一致）
	used_mb=$((total_mb - free_mb))
	pct=$((used_mb * 100 / total_mb))

	echo "内存: ${used_mb}MB / ${total_mb}MB (${pct}%)  空闲 ${free_mb}MB"
	echo "  其中 active ${active_mb}MB / wired ${wired_mb}MB / 压缩器 ${comp_mb}MB   (页大小 $(page_size)B)"
	if [ "$pct" -ge 90 ]; then
		log_error "系统内存占用 ${pct}% —— 极易触发 Jetsam 与交换抖动"
	elif [ "$pct" -ge 75 ]; then
		log_warning "系统内存占用 ${pct}% 偏高"
	fi

	local disk_pct
	disk_pct=$(df -h "$MRRC_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
	case "$disk_pct" in '' | *[!0-9]*) disk_pct=0 ;; esac
	echo "磁盘使用率 (${MRRC_DIR}): ${disk_pct}%"
	if [ "$disk_pct" -ge 95 ]; then
		log_error "磁盘使用率 ${disk_pct}% —— 交换文件/日志将无法扩展（满盘时 IOLoop 写日志会阻塞）"
	elif [ "$disk_pct" -ge 90 ]; then
		log_warning "磁盘使用率 ${disk_pct}% 偏高"
	fi

	# 压力等级与 swap：8GB 机型的主要风险源，必须进 status
	check_pressure_and_swap
	echo ""
}

# 检查网络连接
check_network_status() {
	echo "=== 网络连接状态 ==="

	if lsof -nP -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
		log_success "Web 端口 $WEB_PORT 监听正常"
	else
		log_error "Web 端口 $WEB_PORT 未监听"
	fi

	if lsof -nP -iTCP:"$RIG_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
		log_success "rigctld 端口 ${RIG_HOST}:${RIG_PORT} 监听正常"
	elif [ -n "$RIGCTLD_PID" ]; then
		log_warning "rigctld 进程在运行但 ${RIG_HOST}:${RIG_PORT} 未监听"
	else
		log_note "rigctld 未运行（端口 ${RIG_PORT} 未监听）"
	fi

	local clients
	clients=$(lsof -nP -iTCP:"$WEB_PORT" -sTCP:ESTABLISHED 2>/dev/null | grep -c ESTABLISHED)
	echo "已建立客户端连接: ${clients}"
	if [ "$clients" -eq 0 ] && [ -n "$MRRC_PID" ]; then
		log_note "无浏览器连接：RX 音频/FFT 广播空闲（CPU 应接近基线）"
	fi

	if [ -n "$ATR_DEVICE" ]; then
		if ping -c 1 -W 1000 "$ATR_DEVICE" >/dev/null 2>&1; then
			log_success "ATR-1000 设备 ${ATR_DEVICE} 可达"
		else
			log_warning "ATR-1000 设备 ${ATR_DEVICE} ping 不通"
		fi
		# 端口可达性（ping 通不代表 60001 通：代理崩掉时 ping 仍正常）
		if [ -n "$ATR_PORT" ]; then
			if atr_port_open "$ATR_DEVICE" "$ATR_PORT"; then
				log_success "ATR-1000 端口 ${ATR_DEVICE}:${ATR_PORT} 可连接"
			else
				log_error "ATR-1000 端口 ${ATR_DEVICE}:${ATR_PORT} 不可连接（代理/设备异常）"
			fi
		fi
	fi
	echo ""
}

# 检查日志状态（按实例发现真实日志，而非硬编码已废弃文件名）
check_logs_status() {
	echo "=== 日志文件状态 ==="

	local log seen=0 extras
	# 主实例日志（MRRC.log）与 ATR 通讯日志只在 main 报告里列出，
	# 否则 radio1 报告里混入 main 的日志会误导
	if [ "$INSTANCE" = "main" ]; then
		extras="$MRRC_DIR/MRRC.log $MRRC_DIR/atr1000_comm.log"
	else
		extras=""
	fi
	for log in "$MRRC_LOG" "$RIGCTLD_LOG" "$ATR1000_LOG" $extras; do
		[ -f "$log" ] || continue
		seen=$((seen + 1))
		local size lines
		size=$(ls -lh "$log" | awk '{print $5}')
		lines=$(wc -l <"$log" | tr -d ' ')
		local prev="${log}.prev"
		if [ -f "$prev" ]; then
			echo "✓ $(basename "$log"): ${size}, ${lines} 行, 最后修改 $(stat -f "%Sm" "$log")  (上次运行尾部: $(wc -l <"$prev" | tr -d ' ') 行)"
		else
			echo "✓ $(basename "$log"): ${size}, ${lines} 行, 最后修改 $(stat -f "%Sm" "$log")"
		fi
	done
	[ "$seen" -eq 0 ] && log_warning "未发现任何日志文件（实例 ${INSTANCE}）"

	# 日志增长速率：5 秒窗口，抓刷屏式日志（如每帧一行）
	if [ -f "$MRRC_LOG" ]; then
		local a b
		a=$(stat -f%z "$MRRC_LOG" 2>/dev/null)
		sleep 5
		b=$(stat -f%z "$MRRC_LOG" 2>/dev/null)
		a=${a:-0}
		b=${b:-0}
		local rate=$(((b - a) / 5))
		echo "日志增长: ${rate} 字节/秒 (5 秒窗口)"
		if [ "$rate" -gt 51200 ]; then
			log_error "日志写入 ${rate} B/s 过快，IO 会挤占 IOLoop"
		elif [ "$rate" -gt 10240 ]; then
			log_warning "日志写入 ${rate} B/s 偏快"
		fi
	fi
	echo ""
}

# 检查错误和警告（限定最近 2000 行，避免 3MB 级 rigctld -vvv 日志拖慢）
check_errors_warnings() {
	echo "=== 错误和警告检查 ==="

	local target="$MRRC_LOG"
	if [ ! -f "$target" ]; then
		log_warning "日志不存在: $target"
		echo ""
		return
	fi

	local errors warnings
	errors=$(tail -n 2000 "$target" | grep -icE "error|failed|exception|traceback")
	warnings=$(tail -n 2000 "$target" | grep -icE "warning|⚠️")
	case "$errors" in '' | *[!0-9]*) errors=0 ;; esac
	case "$warnings" in '' | *[!0-9]*) warnings=0 ;; esac
	echo "最近 2000 行: 错误/异常 ${errors} 条, 警告 ${warnings} 条"

	if [ "${errors:-0}" -gt 0 ]; then
		log_warning "MRRC 日志最近 2000 行有 ${errors} 条错误匹配，尾部 5 条:"
		tail -n 2000 "$target" | grep -iE "error|failed|exception|traceback" | tail -5
	fi

	# rigctld 的 -vvv 输出会把正常通信也写成 error，单独轻量统计
	if [ -f "$RIGCTLD_LOG" ]; then
		echo "rigctld 日志尾部错误行: $(tail -n 500 "$RIGCTLD_LOG" | grep -icE "error|failed") (含 -vvv 正常输出，仅供参考)"
	fi
	echo ""
}

# 检查音频设备状态（会打开 CoreAudio —— 蓝牙音频设备在场时慎用）
check_audio_status() {
	echo "=== 音频设备状态 ==="
	log_note "枚举设备会打开 CoreAudio；蓝牙耳机/A2DP 在场时可能引起全局卡顿（RC-001 §7）"

	if ! python3 -c "import pyaudio" 2>/dev/null; then
		log_error "PyAudio 库不可用"
		echo ""
		return
	fi
	log_success "PyAudio 库可用"

	python3 - <<'PYEOF' 2>/dev/null
import pyaudio
p = pyaudio.PyAudio()
try:
    ins, outs = [], []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            ins.append((info['name'], info['maxInputChannels']))
        if info['maxOutputChannels'] > 0:
            outs.append((info['name'], info['maxOutputChannels']))
    print(f"输入设备: {len(ins)} 个")
    for name, ch in ins:
        print(f"  输入: {name} (通道: {ch})")
    print(f"输出设备: {len(outs)} 个")
    for name, ch in outs:
        print(f"  输出: {name} (通道: {ch})")
finally:
    p.terminate()
PYEOF
	echo ""
}

# 每线程 CPU 归因（ps -M 累计时间差分；macOS 唯一可信的线程级方法）
check_cpu_threads() {
	local pid="${MRRC_PID:-}" dur="$1"
	if [ -z "$pid" ]; then
		log_error "MRRC 进程未运行（实例 ${INSTANCE}），无法做线程级归因"
		echo ""
		return
	fi

	echo "=== 每线程 CPU 归因（${dur}s 窗口, PID ${pid}）==="
	echo "方法: ps -M 累计 utime+stime 差分（内核记账）。py-spy 的线程百分比在 macOS 上"
	echo "      是等分伪值（每线程样本数相同），不可用于归因，故不采用。"

	local f1 f2 n1 n2
	f1=$(mktemp "${TMPDIR:-/tmp}/mrrc_mon.XXXXXX")
	f2=$(mktemp "${TMPDIR:-/tmp}/mrrc_mon.XXXXXX")
	thread_cpu_snapshot "$pid" >"$f1"
	n1=$(wc -l <"$f1" | tr -d ' ')
	sleep "$dur"
	thread_cpu_snapshot "$pid" >"$f2"
	n2=$(wc -l <"$f2" | tr -d ' ')

	if [ "$n1" -eq 0 ] || [ "$n2" -eq 0 ]; then
		log_error "无法读取线程计数（ps -M 失败）"
		rm -f "$f1" "$f2"
		echo ""
		return
	fi
	if [ "$n1" -ne "$n2" ]; then
		log_note "窗口内线程数变化 (${n1} → ${n2})，按行号配对可能错位"
	fi

	echo ""
	printf "线程槽\tCPU%%\t累计(s)\n"
	paste "$f1" "$f2" | awk -v d="$dur" -v n1="$n1" '
        { pct = ($2 - $1) / d * 100; cum = $2; idx = NR - 1
          if (pct < 0) pct = 0
          if (pct > 0.005) printf "%d\t%.2f\t%.2f\n", idx, pct, cum
          tot += pct }
        END {
          printf "\n合计: %.2f%% 单核（进程级 %%CPU 应与此一致）\n", tot
          printf "线程槽 0 = 主线程（Tornado IOLoop）：WebSocket/TLS 发送 + 定时器都在此线程。\n"
        }'
	echo "提示: 主线程长期 >5% 单核属偏高；若同时出现 🚨 IOLoop stall，见 RC-001。"
	rm -f "$f1" "$f2"
	echo ""
}

# 内存：进程 footprint（泄漏）+ 系统压力/swap/换页速率（抖动）
check_memory() {
	echo "=== 内存与交换检查 ==="

	# 1) 进程自身
	if [ -n "$MRRC_PID" ]; then
		local fp peak rss threads state_file prev_fp prev_epoch now fpinfo
		fpinfo=$(proc_footprint "$MRRC_PID")
		fp=$(echo "$fpinfo" | awk '{print $1}')
		peak=$(echo "$fpinfo" | awk '{print $2}')
		rss=$(ps -p "$MRRC_PID" -o rss= 2>/dev/null | tr -d ' ')
		threads=$(proc_threads "$MRRC_PID")
		echo "MRRC 进程: RSS $((${rss:-0} / 1024)) MB | footprint ${fp:-?} MB${peak:+ (峰值 ${peak} MB)} | 线程 ${threads}"

		# 与上次调用对比（>5 分钟才有意义），用于发现缓慢泄漏
		state_file="${TMPDIR:-/tmp}/mrrc_monitor_${INSTANCE}.state"
		now=$(date +%s)
		if [ -f "$state_file" ]; then
			read -r prev_epoch prev_fp _ <"$state_file" 2>/dev/null
			if [ -n "$prev_epoch" ] && [ -n "$prev_fp" ] && [ "$fp" != "" ]; then
				local dt=$((now - prev_epoch))
				if [ "$dt" -ge 300 ]; then
					local delta=$((fp - prev_fp))
					local per_hour
					per_hour=$(echo "$delta $dt" | awk '{printf "%.1f", $1 * 3600 / $2}')
					echo "  与上次采样对比: ${delta} MB / $((dt / 60)) 分钟 (≈${per_hour} MB/小时)"
					if [ "$delta" -gt 50 ]; then
						log_warning "footprint 增长 ${delta} MB —— 疑似泄漏，建议长时间观察"
					elif [ "$delta" -lt 0 ]; then
						log_success "footprint 下降/平稳（无泄漏迹象）"
					else
						log_success "footprint 平稳（无泄漏迹象）"
					fi
				fi
			fi
		fi
		printf '%s %s %s\n' "$now" "${fp:-0}" "${rss:-0}" >"$state_file" 2>/dev/null
	else
		log_warning "MRRC 进程未运行，跳过进程内存检查"
	fi

	# 2) 系统
	local psize total_mb free_mb comp_mb pct lvl swap_t swap_u swap_pct
	psize=$(page_size)
	total_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
	free_mb=$(($(vm_stat_val "Pages free") * psize / 1024 / 1024))
	comp_mb=$(($(vm_stat_val "Pages occupied by compressor") * psize / 1024 / 1024))
	pct=$(((total_mb - free_mb) * 100 / total_mb))
	echo ""
	echo "系统内存: ${pct}% 已用（空闲 ${free_mb}MB / 共 ${total_mb}MB，压缩器 ${comp_mb}MB）"

	lvl=$(pressure_level)
	check_pressure_and_swap

	# 3) 换页速率（抖动检测：低内存时磁盘换页会拖死 IOLoop）
	local pi1 po1 pi2 po2 dpi dpo
	pi1=$(vm_stat_val "Pageins")
	po1=$(vm_stat_val "Pageouts")
	sleep 2
	pi2=$(vm_stat_val "Pageins")
	po2=$(vm_stat_val "Pageouts")
	dpi=$((${pi2:-0} - ${pi1:-0}))
	dpo=$((${po2:-0} - ${po1:-0}))
	local mb_in mb_out
	mb_in=$(echo "$dpi $psize" | awk '{printf "%.1f", $1 * $2 / 1048576 / 2}')
	mb_out=$(echo "$dpo $psize" | awk '{printf "%.1f", $1 * $2 / 1048576 / 2}')
	echo "换页速率: 读入 ${mb_in} MB/s, 写出 ${mb_out} MB/s (2 秒窗口)"
	if echo "$mb_in" | awk '{exit !($1 > 40)}'; then
		log_error "换页读入 ${mb_in} MB/s —— 严重抖动（本次实测 8GB 机型失控时约 76 MB/s）"
	elif echo "$mb_in" | awk '{exit !($1 > 10)}'; then
		log_warning "换页读入 ${mb_in} MB/s 偏高"
	else
		log_success "换页速率正常"
	fi

	# 4) 顶耗内存进程（帮用户定位"谁把机器挤没了"）
	echo ""
	echo "内存占用前 6 名（RSS）:"
	ps axo rss=,comm= 2>/dev/null | sort -rn | head -6 | awk '{printf "  %7.0f MB  %s\n", $1/1024, substr($0, index($0,$2), 60)}'
	echo ""
}

# 日志健康标记（watchdog / stall / TX 初始化 / ATR 新鲜度）
check_health() {
	echo "=== 运行健康标记 ==="

	if [ ! -f "$MRRC_LOG" ]; then
		log_warning "日志不存在: $MRRC_LOG"
		echo ""
		return
	fi

	local armed stalls
	# 注意：grep -c 在无匹配时仍会打印 0（但退出码为 1），
	# 所以不能写 `|| echo 0`——那会得到 "0\n0" 并让 [ -gt ] 报 integer expression expected。
	armed=$(grep -c "IOLoop watchdog armed" "$MRRC_LOG" 2>/dev/null)
	case "$armed" in '' | *[!0-9]*) armed=0 ;; esac
	if [ "$armed" -gt 0 ]; then
		log_success "IOLoop watchdog 已启动 (${armed} 次)"
	else
		log_warning "日志中无 'IOLoop watchdog armed'（V6.0.2+ 应每次启动出现）"
	fi

	stalls=$(grep -c "🚨 IOLoop stall" "$MRRC_LOG" 2>/dev/null)
	case "$stalls" in '' | *[!0-9]*) stalls=0 ;; esac
	if [ "$stalls" -gt 0 ]; then
		log_error "检测到 ${stalls} 次事件循环停顿 (🚨 IOLoop stall) —— 见 RC-001"
		grep -A 6 "🚨 IOLoop stall" "$MRRC_LOG" | tail -12
	else
		log_success "无 IOLoop 停顿记录"
	fi

	# TX 初始化耗时（F4b 异步化后的健康指标：p.open < 0.2s 为佳）
	local txline enum_s popen_s
	txline=$(grep -o "⏱️ TX audio init: 枚举 [0-9.]*s, p.open [0-9.]*s" "$MRRC_LOG" 2>/dev/null | tail -1)
	if [ -n "$txline" ]; then
		enum_s=$(echo "$txline" | sed -n 's/.*枚举 \([0-9.]*\)s.*/\1/p')
		popen_s=$(echo "$txline" | sed -n 's/.*p.open \([0-9.]*\)s.*/\1/p')
		echo "最近 TX 初始化: 枚举 ${enum_s}s, p.open ${popen_s}s"
		if echo "${popen_s:-0}" | awk '{exit !($1 > 0.5)}'; then
			log_error "p.open ${popen_s}s 过长 —— CoreAudio 受阻（检查蓝牙音频设备）"
		elif echo "${popen_s:-0}" | awk '{exit !($1 > 0.2)}'; then
			log_warning "p.open ${popen_s}s 偏高（健康值 < 0.2s）"
		else
			log_success "p.open 耗时正常"
		fi
	else
		log_note "日志中暂无 TX 初始化记录（尚未按过 PTT 或日志已轮转）"
	fi

	# 初始化期间的缓冲帧（F4b）
	local flushes
	flushes=$(grep -c "📦 TX init took" "$MRRC_LOG" 2>/dev/null)
	case "$flushes" in '' | *[!0-9]*) flushes=0 ;; esac
	[ "$flushes" -gt 0 ] && echo "TX 初始化缓冲刷新事件: ${flushes} 次（F4b 缓冲路径已生效）"

	# debug 标志（有真实代价，不只是"多打印几行"）
	case "$SERVER_DEBUG" in
	True | true | 1)
		log_warning "[SERVER] debug=True：Tornado autoreload 生效 —— 修改任何 .py 都会重启本实例，且每 500ms 轮询一遍已导入模块的 mtime（本机实测约 0.4% 单核）。生产实例建议 False。"
		;;
	*) log_success "[SERVER] debug 已关闭（无 autoreload 自重启风险）" ;;
	esac
	case "$CTRL_DEBUG" in
	True | true | 1)
		log_note "[CTRL] debug=True：逐条 WebSocket 消息写入日志（本机实测约 0.4 条/秒，CPU 可忽略；仅日志噪声）"
		;;
	esac

	# ATR-1000 数据新鲜度
	local stale
	stale=$(grep -o "最后数据: *[0-9.]*秒前" "$MRRC_LOG" 2>/dev/null | tail -1 | sed -n 's/.*: *\([0-9.]*\)秒前/\1/p')
	if [ -n "$stale" ]; then
		echo "ATR-1000 最后数据: ${stale} 秒前"
		if echo "$stale" | awk '{exit !($1 > 60)}'; then
			log_warning "ATR-1000 数据超过 60 秒未更新"
		fi
	fi

	# 音频/PTT 队列告警（若代码记录了丢弃计数）
	local drops
	drops=$(tail -n 3000 "$MRRC_LOG" 2>/dev/null | grep -cE "丢弃|discard|overflow")
	case "$drops" in '' | *[!0-9]*) drops=0 ;; esac
	[ "$drops" -gt 0 ] && log_note "最近日志中丢弃/溢出记录 ${drops} 条（含 '丢弃' 匹配，需人工确认是否噪声）"
	echo ""
}

###############################################################################
# 报告与实时监控
###############################################################################

verdict_and_exit() {
	echo "=== 判定 ==="
	if [ "$CRIT_COUNT" -gt 0 ]; then
		log_error "严重问题 ${CRIT_COUNT} 项，警告 ${WARN_COUNT} 项"
		return 2
	elif [ "$WARN_COUNT" -gt 0 ]; then
		log_warning "警告 ${WARN_COUNT} 项，无严重问题"
		return 1
	else
		log_success "全部正常"
		return 0
	fi
}

# 单实例完整报告
generate_health_report() {
	local inst="$1"
	load_instance "$inst"

	if [ "${QUIET_HEADER:-0}" != "1" ]; then
		echo "=== MRRC 服务健康报告 ==="
		echo "生成时间: $(date '+%Y-%m-%d %H:%M:%S')   主机: $(hostname -s 2>/dev/null)   $(uname -m)"
		echo ""
	fi

	check_basic_status
	check_system_resources
	check_network_status
	check_logs_status
	check_errors_warnings
	check_health
	# 说明：不调用 check_audio_status —— 枚举设备会打开 CoreAudio（RC-001 §7）。
	# 需要时单独执行: $0 audio

	echo "=== 建议操作 ==="
	if [ -z "$MRRC_PID" ]; then
		echo "❌ 服务未运行，建议执行: ./mrrc_multi.sh start ${inst}"
	else
		echo "✅ 服务运行中"
		local fp
		fp=$(proc_footprint "$MRRC_PID" | awk '{print $1}')
		case "$fp" in '' | *[!0-9]*) fp=0 ;; esac
		if [ "$fp" -gt 1024 ]; then
			echo "⚠️  footprint ${fp} MB 偏高（正常约 100 MB），建议观察是否泄漏"
		fi
		if [ "$INSTANCE" != "main" ]; then
			echo "详情: 每线程 CPU → $0 -i ${inst} cpu ; 内存压力 → $0 -i ${inst} mem"
		fi
	fi

	echo ""
	verdict_and_exit
}

realtime_monitor() {
	local interval="${1:-5}"
	local clear_cmd=""
	if [ -t 1 ]; then
		clear_cmd="clear"
	fi

	local psize total_mb

	echo "启动 MRRC 实时监控（实例 ${INSTANCE}，间隔 ${interval}s）..."
	echo "按 Ctrl+C 退出"
	sleep 1

	while true; do
		[ -n "$clear_cmd" ] && clear
		echo "=== MRRC 实时监控 [${INSTANCE}] - $(date '+%Y-%m-%d %H:%M:%S') ==="
		echo ""

		# 每轮重新解析 PID（进程可能重启）
		MRRC_PID=$(resolve_mrrc_pid "$INSTANCE")

		if [ -n "$MRRC_PID" ]; then
			local cpu mem rss threads uptime fp
			cpu=$(ps -p "$MRRC_PID" -o pcpu= 2>/dev/null | tr -d ' ')
			mem=$(ps -p "$MRRC_PID" -o pmem= 2>/dev/null | tr -d ' ')
			rss=$(ps -p "$MRRC_PID" -o rss= 2>/dev/null | tr -d ' ')
			uptime=$(ps -p "$MRRC_PID" -o etime= 2>/dev/null | tr -d ' ')
			threads=$(proc_threads "$MRRC_PID")
			fp=$(proc_footprint "$MRRC_PID" | awk '{print $1}')
			echo "✅ MRRC (PID ${MRRC_PID})  CPU: ${cpu:-?}% 单核  RSS: $((${rss:-0} / 1024))MB  footprint: ${fp:-?}MB  线程: ${threads}"
			echo "⏰ 运行时间: ${uptime:-?}"
		else
			echo "❌ MRRC 未运行（实例 ${INSTANCE}）"
		fi

		# 端口（用解析出的真实端口，而非硬编码 8899）
		local clients
		clients=$(lsof -nP -iTCP:"$WEB_PORT" -sTCP:ESTABLISHED 2>/dev/null | grep -c ESTABLISHED)
		if lsof -nP -iTCP:"$WEB_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
			echo "🌐 Web: 正常 (端口 ${WEB_PORT}, 客户端 ${clients})"
		else
			echo "🌐 Web: 异常 (端口 ${WEB_PORT} 未监听)"
		fi

		if [ -n "$ATR1000_PID" ]; then
			echo "📡 ATR-1000 代理: 运行中 (PID ${ATR1000_PID})"
		else
			echo "📡 ATR-1000 代理: 未运行"
		fi

		# 系统侧
		echo ""
		print_sys_cpu
		psize=$(page_size)
		total_mb=$(($(sysctl -n hw.memsize) / 1024 / 1024))
		local free_mb pct lvl swap_u swap_t
		free_mb=$(($(vm_stat_val "Pages free") * psize / 1024 / 1024))
		pct=$(((total_mb - free_mb) * 100 / total_mb))
		lvl=$(pressure_level)
		swap_u=$(swap_used_mb)
		swap_t=$(swap_total_mb)
		echo "💾 内存: ${pct}%  (空闲 ${free_mb}MB)  压力等级: ${lvl}  Swap: ${swap_u:-0}/${swap_t:-0}MB"

		echo ""
		echo "刷新中... (${interval}s, Ctrl+C 退出)"
		sleep "$interval"
	done
}

###############################################################################
# 帮助与主程序
###############################################################################

show_help() {
	echo "MRRC 性能与健康监控脚本（本地；远程: ssh <host> \"$0 status\"）"
	echo ""
	echo "用法: $0 [选项] [命令]"
	echo ""
	echo "选项:"
	echo "  -i, --instance <name>  目标实例（main 或 mrrc_multi.sh 创建的实例名，如 radio1）"
	echo "  -a, --all              所有已配置实例（默认: 自动探测，多个实例运行时逐个报告）"
	echo "  -n, --interval <sec>   cpu 采样窗口 / realtime 刷新周期（默认 cpu 10s、realtime 5s）"
	echo "  MRRC_INSTANCE=<name>   环境变量形式指定实例"
	echo ""
	echo "命令:"
	echo "  status    完整健康报告（默认；不含音频枚举）"
	echo "  basic     进程 / 端口 / 伴生进程"
	echo "  system    系统 CPU、内存、磁盘、负载"
	echo "  cpu       每线程 CPU 归因（ps -M 内核记账差分，默认 10s 窗口）"
	echo "  mem       进程 footprint + 内存压力 / swap / 换页速率（泄漏与抖动检测）"
	echo "  health    日志健康标记（watchdog / IOLoop stall / TX p.open / ATR 新鲜度）"
	echo "  network   端口监听、客户端数、ATR 可达性"
	echo "  logs      日志文件与增长速率"
	echo "  errors    最近 2000 行错误/警告"
	echo "  audio     枚举音频设备（会打开 CoreAudio，蓝牙设备在场时慎用）"
	echo "  realtime  实时监控（TTY 下清屏）"
	echo "  help      显示此帮助"
	echo ""
	echo "退出码: 0 正常 / 1 有警告 / 2 有严重问题（所有命令生效，便于 cron/launchd 告警）"
	echo ""
	echo "示例:"
	echo "  $0 -i radio1 status        # radio1 完整报告"
	echo "  $0 -i radio1 cpu 20        # 20 秒线程级 CPU 归因"
	echo "  $0 -a mem                  # 所有实例的内存与交换状况"
	echo "  $0 -i radio1 realtime      # 实时监控 radio1"
}

# 参数解析
TARGET_INSTANCE="${MRRC_INSTANCE:-}"
TARGET_ALL=0
INTERVAL=""
COMMAND=""

while [ $# -gt 0 ]; do
	case "$1" in
	-i | --instance)
		TARGET_INSTANCE="$2"
		shift 2
		;;
	--instance=*)
		TARGET_INSTANCE="${1#*=}"
		shift
		;;
	-a | --all)
		TARGET_ALL=1
		shift
		;;
	-n | --interval)
		INTERVAL="$2"
		shift 2
		;;
	--interval=*)
		INTERVAL="${1#*=}"
		shift
		;;
	-h | --help)
		COMMAND="help"
		shift
		;;
	-*)
		echo "未知选项: $1" >&2
		show_help
		exit 1
		;;
	*)
		COMMAND="$1"
		shift
		# cpu 允许 "cpu 20" 形式覆盖窗口
		if [ -z "$INTERVAL" ] && [ -n "$1" ] && [ "$COMMAND" = "cpu" ]; then
			case "$1" in
			'' | *[!0-9]*) : ;;
			*)
				INTERVAL="$1"
				shift
				;;
			esac
		fi
		break
		;;
	esac
done

COMMAND="${COMMAND:-status}"

# 目标实例集合
INSTANCES=""
if [ "$TARGET_ALL" = "1" ]; then
	INSTANCES=$(list_instances)
	[ -z "$INSTANCES" ] && {
		log_error "未发现任何实例配置 (MRRC*.conf)"
		exit 2
	}
elif [ -n "$TARGET_INSTANCE" ]; then
	# 校验实例名，避免路径穿越（与 mrrc_multi.sh 同一规则）
	case "$TARGET_INSTANCE" in
	*[!A-Za-z0-9_-]* | "")
		log_error "非法实例名: ${TARGET_INSTANCE}（仅允许字母/数字/下划线/连字符）"
		exit 2
		;;
	esac
	if [ "$TARGET_INSTANCE" != "main" ] && [ ! -f "$SCRIPT_DIR/MRRC.${TARGET_INSTANCE}.conf" ]; then
		log_error "实例配置不存在: MRRC.${TARGET_INSTANCE}.conf"
		exit 2
	fi
	INSTANCES="$TARGET_INSTANCE"
else
	# 自动探测：优先唯一运行中的实例，多个则全部报告
	# 注意：不要用 tr -d ' ' 压缩列表——那会把两个实例名粘成一个（radio1radio2）。
	# 这里保留空格分隔，直接用 $running 展开
	running=""
	for inst in $(list_instances); do
		MRRC_PID=$(resolve_mrrc_pid "$inst")
		[ -n "$MRRC_PID" ] && running="$running $inst "
	done
	n_running=$(echo "$running" | wc -w | tr -d ' ')
	case "$n_running" in '' | *[!0-9]*) n_running=0 ;; esac
	if [ "$n_running" -ge 1 ]; then
		INSTANCES=$running
	elif [ -f "$SCRIPT_DIR/MRRC.conf" ]; then
		INSTANCES="main"
	else
		INSTANCES=$(list_instances | head -1)
		[ -z "$INSTANCES" ] && {
			log_error "未发现任何实例配置"
			exit 2
		}
	fi
fi

case "$COMMAND" in
help)
	show_help
	exit 0
	;;
esac

# realtime 为阻塞式，仅支持单实例
if [ "$COMMAND" = "realtime" ]; then
	inst=$(echo "$INSTANCES" | head -1)
	n=$(echo "$INSTANCES" | wc -w | tr -d ' ')
	[ "$n" -gt 1 ] && log_note "realtime 仅支持单实例，显示 ${inst}（用 -i 指定其它实例）"
	load_instance "$inst"
	realtime_monitor "${INTERVAL:-5}"
	exit 0
fi

MULTI=0
n=$(echo "$INSTANCES" | wc -w | tr -d ' ')
[ "$n" -gt 1 ] && MULTI=1

if [ "$COMMAND" = "status" ]; then
	RC=0
	for inst in $INSTANCES; do
		load_instance "$inst"
		[ "$MULTI" = "1" ] && {
			echo ""
			echo "############ 实例: ${inst} ############"
		}
		# 每个实例独立判定，最终退出码取最差
		WARN_COUNT=0
		CRIT_COUNT=0
		generate_health_report "$inst"
		rc=$?
		[ "$rc" -gt "$RC" ] && RC=$rc
	done
	exit "$RC"
fi

RC=0
for inst in $INSTANCES; do
	load_instance "$inst"
	[ "$MULTI" = "1" ] && {
		echo ""
		echo "############ 实例: ${inst} ############"
	}
	case "$COMMAND" in
	basic) check_basic_status ;;
	system) check_system_resources ;;
	cpu) check_cpu_threads "${INTERVAL:-10}" ;;
	mem) check_memory ;;
	health) check_health ;;
	network) check_network_status ;;
	logs) check_logs_status ;;
	errors) check_errors_warnings ;;
	audio) check_audio_status ;;
	*)
		log_error "未知命令: $COMMAND"
		echo ""
		show_help
		exit 2
		;;
	esac
done

# 退出码：所有命令统一按判定计数返回，便于 cron/launchd 告警
if [ "$CRIT_COUNT" -gt 0 ]; then
	exit 2
elif [ "$WARN_COUNT" -gt 0 ]; then
	exit 1
fi

exit 0
