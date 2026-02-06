import matplotlib.pyplot as plt
import numpy as np

# ----------------------------
# Data
# ----------------------------
iters = [0, 1, 2, 3, 4]
x = np.arange(len(iters))

# Accuracy metrics
fex = [81.7, 79.4, 90.1, 77.1, 84.0]
sex = [89.3, 91.3, 91.1, 90.3, 92.4]
rsr = [None, 92.1, 81.4, 79.5, 74.5]  # Iter=0 is "--"

# Cost metrics (token counts are INTEGER)
avg_time = [46.27, 52.27, 58.85, 66.02, 73.96]
avg_tokens = [182400, 189800, 196668, 204900, 212300]  # Iter=2 = measured

# ----------------------------
# Figure & layout
# ----------------------------
fig, (ax_top, ax_bot) = plt.subplots(
    2, 1, figsize=(10.6, 6.8), sharex=True,
    gridspec_kw={'height_ratios': [3.2, 2.6]},
    constrained_layout=False
)

# =========================================================
# Top subplot: Accuracy lines
# =========================================================
l_fex, = ax_top.plot(x, fex, marker='o', linewidth=2, label='FEX (%)')
l_sex, = ax_top.plot(x, sex, marker='s', linewidth=2, label='SEX (%)')

rsr_x = [x[i] for i, v in enumerate(rsr) if v is not None]
rsr_y = [v for v in rsr if v is not None]
l_rsr, = ax_top.plot(rsr_x, rsr_y, marker='^', linewidth=2, label='RSR (%)')

ax_top.set_ylabel('Accuracy Metrics (%)')
ax_top.set_title('Semantic Repair Iterations: Accuracy and Cost')

# 上图也要横轴
ax_top.set_xlabel('Number of Semantic Repair Iterations (Iter)')
ax_top.set_xticks(x)
ax_top.set_xticklabels(iters)

top_vals = fex + sex + rsr_y
ax_top.set_ylim(min(top_vals) - 3.0, max(top_vals) + 4.5)

# ---- staggered annotations ----
rsr_aligned = [None, 92.1, 81.4, 79.5, 74.5]

def annotate_lines_staggered(ax, xs, series_list, fmts, close_thresh=1.2):
    per_x = {xi: [] for xi in xs}
    for si, ys in enumerate(series_list):
        for i, xi in enumerate(xs):
            y = ys[i]
            if y is not None:
                per_x[xi].append((si, y))

    for si, ys in enumerate(series_list):
        for i, xi in enumerate(xs):
            y = ys[i]
            if y is None:
                continue

            bucket = sorted(per_x[xi], key=lambda t: t[1])
            order = [b[0] for b in bucket]
            rank = order.index(si)

            dy = -1.0 if rank % 2 == 0 else 1.0
            va = 'top' if dy < 0 else 'bottom'

            if len(bucket) > 1:
                dmin = min(abs(y - yj) for sj, yj in bucket if sj != si)
                if dmin < close_thresh:
                    dy *= 1.7

            dx = (rank - (len(bucket) - 1) / 2) * 0.06

            ax.text(
                xi + dx, y + dy,
                fmts[si].format(y),
                ha='center', va=va, fontsize=8
            )

annotate_lines_staggered(
    ax_top,
    xs=x,
    series_list=[fex, sex, rsr_aligned],
    fmts=['{:.1f}', '{:.1f}', '{:.1f}']
)

# =========================================================
# Bottom subplot: Cost bars (Time + Tokens)
# =========================================================
bar_w = 0.36
colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
time_color = colors[0]
tok_color = colors[1]

b_time = ax_bot.bar(
    x - bar_w/2, avg_time, width=bar_w,
    label='Avg Time (s)', color=time_color
)
ax_bot.set_ylabel('Avg Time (s)')

ax_bot_r = ax_bot.twinx()
b_tok = ax_bot_r.bar(
    x + bar_w/2, avg_tokens, width=bar_w,
    label='Avg Tokens', color=tok_color
)
ax_bot_r.set_ylabel('Avg Tokens')

ax_bot.set_ylim(0, max(avg_time) * 1.22)
ax_bot_r.set_ylim(0, max(avg_tokens) * 1.30)

# ---- annotate bars (INTEGER tokens) ----
def annotate_bars(ax, bars, fmt, dy):
    for b in bars:
        h = b.get_height()
        ax.text(
            b.get_x() + b.get_width()/2,
            h + dy,
            fmt.format(int(h)),
            ha='center', va='bottom', fontsize=8
        )

annotate_bars(ax_bot, b_time, '{:.2f}', dy=max(avg_time) * 0.02)
annotate_bars(ax_bot_r, b_tok, '{:d}', dy=max(avg_tokens) * 0.03)

ax_bot.set_xticks(x)
ax_bot.set_xticklabels(iters)
ax_bot.set_xlabel('Number of Semantic Repair Iterations (Iter)')

# =========================================================
# Legend outside
# =========================================================
handles = [l_fex, l_sex, l_rsr, b_time, b_tok]
labels = [h.get_label() for h in handles]

fig.subplots_adjust(right=0.78, hspace=0.28, top=0.92, bottom=0.10)

fig.legend(
    handles, labels,
    loc='center left',
    bbox_to_anchor=(0.80, 0.5),
    frameon=False
)

plt.show()
