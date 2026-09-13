#!/usr/bin/env bash
# 构建"带内部 dump"的临时调试库（不改动生产源码）；供 nr2_internals.py 等使用。
# 用法: bash dev_tools/wdsp_debug_build.sh  → /tmp/wdsp_dbg/libwdsp.dylib
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf /tmp/wdsp_dbg
cp -a "$ROOT/DSP/wdsp" /tmp/wdsp_dbg
python3 - <<'PY'
p = '/tmp/wdsp_dbg/emnr.c'
s = open(p).read()
s = s.rstrip() + '''

/* DEV only: dump EMNR internals for NR2 analysis (not in production source) */
PORT void emnr_dump (int channel, int what, double* out, int* msize)
{
	EMNR a = rxa[channel].emnr.p;
	int k;
	*msize = a->msize;
	for (k = 0; k < a->msize; k++)
	{
		switch (what)
		{
		case 0: out[k] = a->g.lambda_y[k];   break;
		case 1: out[k] = a->g.lambda_d[k];   break;
		case 2: out[k] = a->mask[k];         break;
		case 3: out[k] = a->np.p[k];         break;
		case 4: out[k] = a->np.sigma2N[k];   break;
		case 5: out[k] = a->g.prev_gamma[k]; break;
		case 6: out[k] = a->np.alphaHat[k];  break;
		case 7: out[k] = a->g.max_atten;     break;
		case 8: out[k] = a->g.dry;           break;
		case 9: out[k] = a->g.npe_method;    break;
		}
	}
}
'''
open(p, 'w').write(s)
PY
cd /tmp/wdsp_dbg && make CFLAGS="-I/opt/local/include" >/dev/null && echo "调试库: /tmp/wdsp_dbg/libwdsp.dylib"
