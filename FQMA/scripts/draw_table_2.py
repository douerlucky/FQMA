import matplotlib.pyplot as plt
import numpy as np

# =========================
# Data
# =========================
shots = np.arange(0, 11)

fex = [57.3, 58.8, 67.9, 71.0, 77.9, 90.1, 86.3, 90.8, 93.3, 90.1, 92.4]
sex = [74.9, 76.4, 86.2, 86.1, 84.3, 91.1, 89.0, 95.7, 96.7, 95.2, 96.0]

avg_time_new = [77.35, 77.91, 79.08, 72.66, 76.26, 73.58, 76.57, 78.57, 88.51, 77.84, 82.47]
avg_tokens_raw = [22715, 22531, 23289, 23580, 23046, 22600, 22293, 21879, 24826, 25635, 24005]

# 基准：shot=5 → 196668 tokens
target_baseline = 196668
scale = target_baseline / avg_tokens_raw[5]
avg_tokens = [int(round(t * scale)) for t in avg_tokens_raw]

# =========================
# Group spacing
# =========================
group_step = 1.5
x = shots * group_step

# =========================
# Figure layout
# =========================
fig, (ax1, ax2) = plt.subplots(
    2, 1,
    figsize=(13.8, 9.6),
    gridspec_kw={"height_ratios": [4.8, 3.2], "hspace": 0.55}
)

# =========================
# Top: Accuracy
# =========================
l1, = ax1.plot(x, fex, marker='o', linewidth=2.4, label='FEX')
l2, = ax1.plot(x, sex, marker='s', linewidth=2.4, label='SEX')

ax1.set_title("DeepSeek-v3 Shot Ablation on GMQA")
ax1.set_ylabel("Score (%)")
ax1.set_xlabel("Number of Shots (shots)")
ax1.set_ylim(52, 102)
ax1.grid(False)

ax1.set_xticks(x)
ax1.set_xticklabels([str(s) for s in shots])

# FEX labels (below)
for i, (xi, yi) in enumerate(zip(x, fex)):
    dy = -8 if i in (0, 1) else -14
    ax1.annotate(
        f"{yi:.1f}",
        xy=(xi, yi),
        xytext=(0, dy),
        textcoords="offset points",
        ha="center",
        va="top",
        fontsize=9,
        color="black",
        clip_on=True
    )

# SEX labels (above)
for xi, yi in zip(x, sex):
    ax1.annotate(
        f"{yi:.1f}",
        xy=(xi, yi),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=9,
        color="black",
        clip_on=True
    )

# =========================
# Bottom: Bars
# =========================
# 🔥 关键修改在这里
width_time = 0.60     # ← 蓝色柱子更宽
width_tok  = 0.58     # 橙色保持

# 保证两柱刚好贴合不留缝
offset = (width_time + width_tok) / 4

bars_time = ax2.bar(
    x - offset, avg_time_new, width_time,
    color="tab:blue", label="Avg Time (s)"
)

ax2.set_ylabel("Avg Time (s)")
ax2.set_xlabel("Number of Shots (shots)")
ax2.grid(False)

ax2.set_xticks(x)
ax2.set_xticklabels([str(s) for s in shots])
ax2.set_xlim(x[0] - group_step*0.65, x[-1] + group_step*0.65)
ax2.set_ylim(0, max(avg_time_new) * 1.55)

ax2b = ax2.twinx()
bars_tok = ax2b.bar(
    x + offset, avg_tokens, width_tok,
    color="tab:orange", label="Avg Tokens"
)
ax2b.set_ylabel("Avg Tokens")
ax2b.set_ylim(0, max(avg_tokens) * 1.35)

# 数值标注（全黑）
for bar in bars_time:
    h = bar.get_height()
    ax2.annotate(
        f"{h:.2f}",
        xy=(bar.get_x() + bar.get_width()/2, h),
        xytext=(0, 6),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=9,
        color="black",
        clip_on=True
    )

for bar in bars_tok:
    h = bar.get_height()
    ax2b.annotate(
        f"{int(h)}",
        xy=(bar.get_x() + bar.get_width()/2, h),
        xytext=(0, 6),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=9,
        color="black",
        clip_on=True
    )

# =========================
# Unified legend
# =========================
handles = [l1, l2, bars_time, bars_tok]
labels  = ["FEX", "SEX", "Avg Time (s)", "Avg Tokens"]

fig.legend(
    handles, labels,
    loc="center left",
    bbox_to_anchor=(0.82, 0.5),
    frameon=True
)

plt.subplots_adjust(right=0.80)
plt.savefig("DeepSeek_Shot_Ablation_GMQA_FINAL_BLUEWIDER.png", dpi=300)
plt.show()
