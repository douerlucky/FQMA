import matplotlib.pyplot as plt
import numpy as np

# ----------------------------
# Data
# ----------------------------
settings = [
    "No Repair\n(-Syntax, -Semantic)",
    "Syntax Only\n(+Syntax, -Semantic)",
    "Semantic Only\n(-Syntax, +Semantic)",
    "Full System\n(+Syntax, +Semantic)"
]
x = np.arange(len(settings))

fex = [73.7, 78.9, 84.2, 90.1]
sex = [82.9, 85.96, 89.47, 91.1]

avg_time = [26.13, 28.27, 35.55, 54.51]
avg_tokens = [55067, 106201, 145534, 196668]

# ----------------------------
# Figure layout
# ----------------------------
fig, (ax_top, ax_bot) = plt.subplots(
    2, 1, figsize=(10.8, 7.0), sharex=True,
    gridspec_kw={'height_ratios': [3.0, 2.8]}
)

bar_w = 0.36

# =========================================================
# Top subplot: Accuracy bars
# =========================================================
b_fex = ax_top.bar(x - bar_w/2, fex, width=bar_w,
                   color='#4C72B0', label='FEX (%)')
b_sex = ax_top.bar(x + bar_w/2, sex, width=bar_w,
                   color='#DD8452', label='SEX (%)')

ax_top.set_ylabel('Accuracy (%)')
ax_top.set_ylim(70, 95)
ax_top.set_title('Repair Component Ablation: Accuracy and Cost')

# ✅ 关键修复 1：显式设置刻度
ax_top.set_xticks(x)
ax_top.set_xticklabels(settings)

# ✅ 关键修复 2：强制显示上图 x tick labels
ax_top.tick_params(axis='x', labelbottom=True)

ax_top.set_xlabel('System Setting')

def annotate(ax, bars, fmt, dy):
    for b in bars:
        h = b.get_height()
        ax.text(
            b.get_x() + b.get_width()/2,
            h + dy,
            fmt.format(h),
            ha='center', va='bottom', fontsize=8
        )

annotate(ax_top, b_fex, '{:.1f}', 0.8)
annotate(ax_top, b_sex, '{:.2f}', 0.8)

# =========================================================
# Bottom subplot: Cost bars (TWO colors only)
# =========================================================
b_time = ax_bot.bar(
    x - bar_w/2, avg_time, width=bar_w,
    color='#55A868', label='Avg Time (s)'
)
ax_bot.set_ylabel('Avg Time (s)')

ax_bot_r = ax_bot.twinx()
b_tok = ax_bot_r.bar(
    x + bar_w/2, avg_tokens, width=bar_w,
    color='#C44E52', label='Avg Tokens / Query'
)
ax_bot_r.set_ylabel('Avg Tokens / Query')

ax_bot.set_ylim(0, max(avg_time) * 1.25)
ax_bot_r.set_ylim(0, max(avg_tokens) * 1.15)

annotate(ax_bot, b_time, '{:.2f}', max(avg_time) * 0.03)
annotate(ax_bot_r, b_tok, '{:,.0f}', max(avg_tokens) * 0.03)

# Bottom x-axis
ax_bot.set_xticks(x)
ax_bot.set_xticklabels(settings)
ax_bot.set_xlabel('System Setting')

# =========================================================
# Legend
# =========================================================
handles = [b_fex, b_sex, b_time, b_tok]
labels = ['FEX (%)', 'SEX (%)', 'Avg Time (s)', 'Avg Tokens / Query']

fig.subplots_adjust(right=0.78, hspace=0.35, top=0.92, bottom=0.12)
fig.legend(
    handles, labels,
    loc='center left',
    bbox_to_anchor=(0.80, 0.5),
    frameon=False
)

plt.show()
