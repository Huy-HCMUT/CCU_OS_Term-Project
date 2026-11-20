# Realistic-Load Comparison: Phase 6a (A, B, B-iso) and Phase 6b (C act) under R-net, R-deploy & R-both

## Timing Summary

| Series | Tier | n runs | Cycles | WCL µs mean [min–max] | Block WCL median µs | σ_L µs mean | DMR@1 ms max % | Ref 0% WCL µs mean [min–max] | Ref all-core WCL µs mean [min–max] |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | rdeploy | 2 | 180000 | 13394.7 [11826.7–14962.7] | 5817.5 | 403.0 | 1.55 | 544.9 [520.5–562.6] | 21579.7 [18000.4–27851.9] |
| A | rnet | 2 | 180000 | 1601.1 [1489.4–1712.8] | 604.9 | 101.3 | 0.00 | 544.9 [520.5–562.6] | 21579.7 [18000.4–27851.9] |
| A | rboth | 2 | 180000 | 9547.2 [8364.1–10730.3] | 5572.3 | 387.4 | 4.72 | 544.9 [520.5–562.6] | 21579.7 [18000.4–27851.9] |
| B | rdeploy | 2 | 180000 | 533.2 [518.8–547.7] | 140.2 | 29.6 | 0.00 | 470.5 [433.2–516.4] | 661.0 [552.4–769.9] |
| B | rnet | 2 | 180000 | 1073.6 [989.6–1157.6] | 753.6 | 96.6 | 0.00 | 470.5 [433.2–516.4] | 661.0 [552.4–769.9] |
| B | rboth | 2 | 180000 | 1492.4 [1445.9–1538.8] | 301.3 | 62.1 | 0.04 | 470.5 [433.2–516.4] | 661.0 [552.4–769.9] |
| B-iso | rdeploy | 2 | 180000 | 610.0 [568.3–651.7] | 386.0 | 29.8 | 0.00 | 95.9 [90.0–107.6] | 323.6 [275.0–388.1] |
| B-iso | rnet | 2 | 180000 | 789.2 [757.5–820.8] | 528.5 | 13.2 | 0.00 | 95.9 [90.0–107.6] | 323.6 [275.0–388.1] |
| B-iso | rboth | 2 | 180000 | 1658.0 [1591.3–1724.7] | 1452.1 | 161.9 | 0.31 | 95.9 [90.0–107.6] | 323.6 [275.0–388.1] |
| C act tuned | 0 | 2 | 10000 | 6.7 [6.3–7.0] | 6.7 | 0.5 | 0.00 | – | – |
| C act tuned | rdeploy | 2 | 10000 | 7.6 [7.0–8.2] | 7.6 | 0.7 | 0.00 | – | – |
| C act tuned | rnet | 2 | 10000 | 8.2 [8.1–8.3] | 8.2 | 0.9 | 0.00 | – | – |
| C act tuned | rboth | 2 | 10000 | 9.1 [7.6–10.5] | 9.1 | 0.9 | 0.00 | – | – |

## Load Evidence Per Run

| File | Series | Tier | Rep | wlan0 rx Δ (B) | NET_RX Δ | IRQ total Δ | Top IRQ | Temp max °C | Freq min kHz | Throttled | Inferences / rate Hz / p50–p99 µs | PC traffic B/s / reconn | Loadcheck | IRQ / Wi-Fi affinity |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: | ---: | :--- | :--- | :--- | :--- | :--- |
| real_r1/A_0_rboth.csv | A | rboth | 1 | 12207027820 | 216834 | 4404552 | 13(GICv3 19 Level arch_timer)=1903502[610054,472014,445730,375704] | 62.6 | 2016000 | False | 21573 / 11.72 / 46075–59103 | 5786587 / 158 + ingest 44183 / skips 3 | loadcheck start: LOADCHECK OK tier=rboth rx_Bps=6707448 inferences=60; loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6635251 inferences=60; loadcheck end: LOADCHECK OK tier=rboth rx_Bps=6643947 inferences=60 | — |
| real_r1/A_0_rdeploy.csv | A | rdeploy | 1 | 98767960 | 298903 | 3352113 | 13(GICv3 19 Level arch_timer)=1695957[353248,467571,459384,415754] | 60.7 | 2016000 | False | 21571 / 11.72 / 43383–48448 | 36814 / 558 | loadcheck start: LOADCHECK OK tier=rdeploy rx_Bps=53974 inferences=60; loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=53865 inferences=60; loadcheck end: LOADCHECK OK tier=rdeploy rx_Bps=53661 inferences=48 | — |
| real_r1/A_0_rnet.csv | A | rnet | 1 | 11981533166 | 4198 | 4866305 | IPI1(Function call interrupts)=1633664[161690,645969,451901,374104] | 44.3 | 2016000 | False | — | 4856478 / 560 | loadcheck start: LOADCHECK OK tier=rnet rx_Bps=6666756 inferences=-; loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6610825 inferences=-; loadcheck end: LOADCHECK OK tier=rnet rx_Bps=6642882 inferences=- | — |
| real_r1/B_0_iso_rboth.csv | B-iso | rboth | 1 | 12050970568 | 216399 | 5952195 | 13(GICv3 19 Level arch_timer)=1944586[423149,414605,427635,679197] | 61.6 | 2016000 | False | 21573 / 11.72 / 47899–65338 | 5786587 / 158 + ingest 44183 / skips 3 | loadcheck start: LOADCHECK OK tier=rboth rx_Bps=6611788 inferences=60; loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6687523 inferences=60; loadcheck end: LOADCHECK OK tier=rboth rx_Bps=6320381 inferences=60 | irqs_moved=51 of 81; wifi_irq 140 effective=0; wifi_irq 141 effective=0; wifi_irq 142 effective=0; wifi_irq 143 effective=0; wifi_irq 144 effective=0; wifi_irq 145 effective=0; wifi_irq 146 effective=0; wifi_irq 147 effective=0; wifi_irq 148 effective=0; wifi_irq 149 effective=0; wifi_irq 150 effective=0; wifi_irq 151 effective=0 |
| real_r1/B_0_iso_rdeploy.csv | B-iso | rdeploy | 1 | 98960396 | 313966 | 3245278 | 13(GICv3 19 Level arch_timer)=1851972[436469,406345,379541,629617] | 60.4 | 2016000 | False | 21569 / 11.71 / 37246–46156 | 36814 / 558 | loadcheck start: LOADCHECK OK tier=rdeploy rx_Bps=53958 inferences=60; loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=53592 inferences=60; loadcheck end: LOADCHECK OK tier=rdeploy rx_Bps=53955 inferences=60 | irqs_moved=51 of 81; wifi_irq 140 effective=0; wifi_irq 141 effective=0; wifi_irq 142 effective=0; wifi_irq 143 effective=0; wifi_irq 144 effective=0; wifi_irq 145 effective=0; wifi_irq 146 effective=0; wifi_irq 147 effective=0; wifi_irq 148 effective=0; wifi_irq 149 effective=0; wifi_irq 150 effective=0; wifi_irq 151 effective=0 |
| real_r1/B_0_iso_rnet.csv | B-iso | rnet | 1 | 12252404986 | 3373 | 4577273 | IPI1(Function call interrupts)=1837651[296140,1009314,411369,120828] | 44.3 | 2016000 | False | — | 4856478 / 560 | loadcheck start: LOADCHECK OK tier=rnet rx_Bps=6572542 inferences=-; loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6657708 inferences=-; loadcheck end: LOADCHECK OK tier=rnet rx_Bps=6721666 inferences=- | irqs_moved=51 of 81; wifi_irq 140 effective=0; wifi_irq 141 effective=0; wifi_irq 142 effective=0; wifi_irq 143 effective=0; wifi_irq 144 effective=0; wifi_irq 145 effective=0; wifi_irq 146 effective=0; wifi_irq 147 effective=0; wifi_irq 148 effective=0; wifi_irq 149 effective=0; wifi_irq 150 effective=0; wifi_irq 151 effective=0 |
| real_r1/B_0_rboth.csv | B | rboth | 1 | 12044296418 | 212464 | 4370162 | 13(GICv3 19 Level arch_timer)=1907728[467639,631626,393942,414521] | 62.6 | 2016000 | False | 21573 / 11.72 / 46925–58754 | 5786587 / 158 + ingest 44183 / skips 3 | loadcheck start: LOADCHECK OK tier=rboth rx_Bps=6652674 inferences=60; loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6582588 inferences=60; loadcheck end: LOADCHECK OK tier=rboth rx_Bps=6614587 inferences=60 | — |
| real_r1/B_0_rdeploy.csv | B | rdeploy | 1 | 98744810 | 313813 | 3405408 | 13(GICv3 19 Level arch_timer)=1689137[314178,283501,461463,629995] | 62.3 | 2016000 | False | 21570 / 11.72 / 38492–41336 | 36814 / 558 | loadcheck start: LOADCHECK OK tier=rdeploy rx_Bps=53806 inferences=60; loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=53901 inferences=60; loadcheck end: LOADCHECK OK tier=rdeploy rx_Bps=53670 inferences=48 | — |
| real_r1/B_0_rnet.csv | B | rnet | 1 | 12033273061 | 4071 | 4710958 | IPI1(Function call interrupts)=1589798[185862,636941,542382,224613] | 47.1 | 2016000 | False | — | 4856478 / 560 | loadcheck start: LOADCHECK OK tier=rnet rx_Bps=6656500 inferences=-; loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6756744 inferences=-; loadcheck end: LOADCHECK OK tier=rnet rx_Bps=6653769 inferences=- | — |
| real_r2/A_0_rboth.csv | A | rboth | 2 | 11925088176 | 217557 | 4728396 | 13(GICv3 19 Level arch_timer)=1920345[520973,516024,446602,436746] | 64.5 | 2016000 | False | 21573 / 11.72 / 39334–54990 | 5725180 / 159 + ingest 44180 / skips 3 | loadcheck start: LOADCHECK OK tier=rboth rx_Bps=6615299 inferences=60; loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6578456 inferences=60; loadcheck end: LOADCHECK OK tier=rboth rx_Bps=6387291 inferences=60 | — |
| real_r2/A_0_rdeploy.csv | A | rdeploy | 2 | 98313985 | 299788 | 3327477 | 13(GICv3 19 Level arch_timer)=1606562[417714,427658,334557,426633] | 61.9 | 2016000 | False | 21458 / 11.66 / 38242–41974 | 36756 / 558 | loadcheck start: LOADCHECK OK tier=rdeploy rx_Bps=53913 inferences=60; loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=46554 inferences=54; loadcheck end: LOADCHECK OK tier=rdeploy rx_Bps=53592 inferences=60 | — |
| real_r2/A_0_rnet.csv | A | rnet | 2 | 11806901449 | 4045 | 4739687 | IPI1(Function call interrupts)=1592528[179927,636428,419073,357100] | 43.4 | 2016000 | False | — | 5749788 / 160 | loadcheck start: LOADCHECK OK tier=rnet rx_Bps=6656750 inferences=-; loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6511142 inferences=-; loadcheck end: LOADCHECK OK tier=rnet rx_Bps=6431703 inferences=- | — |
| real_r2/B_0_iso_rboth.csv | B-iso | rboth | 2 | 12022672902 | 224329 | 6020690 | 13(GICv3 19 Level arch_timer)=1927965[403470,404318,445196,674981] | 64.8 | 2016000 | False | 21571 / 11.72 / 41749–62208 | 5725180 / 159 + ingest 44180 / skips 3 | loadcheck start: LOADCHECK OK tier=rboth rx_Bps=6680920 inferences=60; loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6705836 inferences=60; loadcheck end: LOADCHECK OK tier=rboth rx_Bps=6424478 inferences=60 | irqs_moved=51 of 81; wifi_irq 140 effective=0; wifi_irq 141 effective=0; wifi_irq 142 effective=0; wifi_irq 143 effective=0; wifi_irq 144 effective=0; wifi_irq 145 effective=0; wifi_irq 146 effective=0; wifi_irq 147 effective=0; wifi_irq 148 effective=0; wifi_irq 149 effective=0; wifi_irq 150 effective=0; wifi_irq 151 effective=0 |
| real_r2/B_0_iso_rdeploy.csv | B-iso | rdeploy | 2 | 98778903 | 319388 | 3225545 | 13(GICv3 19 Level arch_timer)=1861623[438194,387671,416076,619682] | 59.7 | 2016000 | False | 21576 / 11.72 / 37113–46907 | 36756 / 558 | loadcheck start: LOADCHECK OK tier=rdeploy rx_Bps=53932 inferences=60; loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=53613 inferences=60; loadcheck end: LOADCHECK OK tier=rdeploy rx_Bps=54106 inferences=60 | irqs_moved=51 of 81; wifi_irq 140 effective=0; wifi_irq 141 effective=0; wifi_irq 142 effective=0; wifi_irq 143 effective=0; wifi_irq 144 effective=0; wifi_irq 145 effective=0; wifi_irq 146 effective=0; wifi_irq 147 effective=0; wifi_irq 148 effective=0; wifi_irq 149 effective=0; wifi_irq 150 effective=0; wifi_irq 151 effective=0 |
| real_r2/B_0_iso_rnet.csv | B-iso | rnet | 2 | 12042248948 | 3325 | 4500900 | IPI1(Function call interrupts)=1787883[283282,993691,407533,103377] | 43.4 | 2016000 | False | — | 5749788 / 160 | loadcheck start: LOADCHECK OK tier=rnet rx_Bps=5760186 inferences=-; loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6322654 inferences=-; loadcheck end: LOADCHECK OK tier=rnet rx_Bps=6604563 inferences=- | irqs_moved=51 of 81; wifi_irq 140 effective=0; wifi_irq 141 effective=0; wifi_irq 142 effective=0; wifi_irq 143 effective=0; wifi_irq 144 effective=0; wifi_irq 145 effective=0; wifi_irq 146 effective=0; wifi_irq 147 effective=0; wifi_irq 148 effective=0; wifi_irq 149 effective=0; wifi_irq 150 effective=0; wifi_irq 151 effective=0 |
| real_r2/B_0_rboth.csv | B | rboth | 2 | 11974630122 | 217464 | 4638896 | 13(GICv3 19 Level arch_timer)=1914469[458901,447660,416039,591869] | 64.5 | 2016000 | False | 21571 / 11.72 / 39438–53704 | 5725180 / 159 + ingest 44180 / skips 3 | loadcheck start: LOADCHECK OK tier=rboth rx_Bps=6476036 inferences=60; loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6497894 inferences=60; loadcheck end: LOADCHECK OK tier=rboth rx_Bps=6536893 inferences=60 | — |
| real_r2/B_0_rdeploy.csv | B | rdeploy | 2 | 98788825 | 312867 | 3163406 | 13(GICv3 19 Level arch_timer)=1623101[382286,417894,636193,186728] | 61.9 | 2016000 | False | 21574 / 11.72 / 38575–42925 | 36756 / 558 | loadcheck start: LOADCHECK OK tier=rdeploy rx_Bps=53954 inferences=60; loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=54035 inferences=60; loadcheck end: LOADCHECK OK tier=rdeploy rx_Bps=53663 inferences=48 | — |
| real_r2/B_0_rnet.csv | B | rnet | 2 | 11929371929 | 4679 | 4577460 | IPI1(Function call interrupts)=1473747[133887,591435,320703,427722] | 44.3 | 2016000 | False | — | 5749788 / 160 | loadcheck start: LOADCHECK OK tier=rnet rx_Bps=6708996 inferences=-; loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6203949 inferences=-; loadcheck end: LOADCHECK OK tier=rnet rx_Bps=6460068 inferences=- | — |
| act_tuned/C_0_act_tuned.csv | C act tuned | 0 | 1 | — | — | — | — | — | — | — | — | — | — | — |
| act_tuned_r2/C_0_act_tuned.csv | C act tuned | 0 | 2 | — | — | — | — | — | — | — | — | — | — | — |
| act_tuned_rdeploy/C_0_act_tuned_rdeploy.csv | C act tuned | rdeploy | 1 | 7576604 | 24159 | 373875 | 13(GICv3 19 Level arch_timer)=226353[49125,78260,38905,60063] | 56.3 | 2016000 | False | 1652 / 11.72 / 38379–45421 | 47767 / 0 | loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=54056 inferences=48 | — |
| act_tuned_rdeploy_r2/C_0_act_tuned_rdeploy.csv | C act tuned | rdeploy | 2 | 7534515 | 24269 | 367449 | 13(GICv3 19 Level arch_timer)=223201[38308,73195,37138,74560] | 56.9 | 2016000 | False | 1650 / 11.72 / 38251–47823 | 47774 / 0 | loadcheck mid: LOADCHECK OK tier=rdeploy rx_Bps=53662 inferences=60 | — |
| act_tuned_rnet/C_0_act_tuned_rnet.csv | C act tuned | rnet | 1 | 902626562 | 598 | 451373 | 13(GICv3 19 Level arch_timer)=178767[52013,42064,41270,43420] | 41.2 | 1305600 | False | — | 6153982 / 0 | loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6661915 inferences=- | — |
| act_tuned_rnet_r2/C_0_act_tuned_rnet.csv | C act tuned | rnet | 2 | 961857308 | 640 | 470999 | 13(GICv3 19 Level arch_timer)=183399[52069,43227,46474,41629] | 41.2 | 1305600 | False | — | 6559664 / 0 | loadcheck mid: LOADCHECK OK tier=rnet rx_Bps=6755255 inferences=- | — |
| act_tuned_rboth/C_0_act_tuned_rboth.csv | C act tuned | rboth | 1 | 935836354 | 16851 | 463193 | 13(GICv3 19 Level arch_timer)=242167[51487,63413,82922,44345] | 58.8 | 2016000 | False | 1653 / 11.72 / 39712–64003 | 6311293 / 0 + ingest 47781 / skips 1 | loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6624579 inferences=60 | — |
| act_tuned_rboth_r2/C_0_act_tuned_rboth.csv | C act tuned | rboth | 2 | 968301006 | 17510 | 470774 | 13(GICv3 19 Level arch_timer)=242310[89746,47391,54693,50480] | 59.1 | 2016000 | False | 1649 / 11.72 / 42062–73124 | 6534236 / 0 + ingest 47637 / skips 1 | loadcheck mid: LOADCHECK OK tier=rboth rx_Bps=6819345 inferences=60 | — |

## Kernel work on CPU 3

| Series | Tier | n runs | dev_irq | ipi_resched | ipi_call | ipi_tbcast | softirq_timer | softirq_net_rx | softirq_sched | softirq_rcu |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | rnet | 2 | 150 [150–151] | 1 [1–1] | 199 [194–203] | 31 [31–32] | 16 [15–17] | 0 [0–0] | 63 [63–64] | 70 [69–70] |
| A | rdeploy | 2 | 263 [239–286] | 1 [0–1] | 48 [28–68] | 4 [3–4] | 17 [6–28] | 17 [5–28] | 38 [26–49] | 160 [142–178] |
| A | rboth | 2 | 242 [232–252] | 14 [10–18] | 87 [56–118] | 3 [1–4] | 14 [9–18] | 20 [11–28] | 45 [31–60] | 151 [135–167] |
| B | rnet | 2 | 165 [126–204] | 1 [1–1] | 177 [122–232] | 31 [27–34] | 17 [11–23] | 0 [0–0] | 62 [59–64] | 67 [58–75] |
| B | rdeploy | 2 | 251 [155–347] | 1 [0–2] | 88 [9–167] | 10 [1–18] | 18 [9–26] | 25 [4–47] | 62 [13–111] | 149 [100–198] |
| B | rboth | 2 | 290 [239–341] | 9 [9–10] | 60 [59–60] | 4 [3–5] | 10 [9–10] | 13 [13–14] | 37 [35–38] | 159 [151–167] |
| B-iso | rnet | 2 | 178 [177–179] | 0 [0–0] | 61 [56–66] | 0 [0–0] | 28 [27–30] | 0 [0–0] | 30 [30–30] | 36 [35–37] |
| B-iso | rdeploy | 2 | 342 [338–347] | 1 [1–1] | 235 [234–236] | 1 [0–1] | 111 [110–112] | 80 [77–84] | 82 [80–83] | 87 [85–88] |
| B-iso | rboth | 2 | 371 [370–372] | 6 [5–6] | 654 [642–665] | 0 [0–0] | 119 [118–119] | 76 [75–77] | 138 [135–140] | 105 [103–107] |

(1) B-iso pins the control thread to CPU 3 and moves our load, the sampler and the movable IRQs to CPUs 0–2; A and B are not pinned, so for them CPU 3 is the same core for comparison only; (2) isolation is by affinity only: no `isolcpus`, `nohz_full` or `rcu_nocbs` on the kernel command line (checked 2026-11-18); (3) the counters are whole-run before/after snapshots (incl. the 30 s warm-up), so the rates are run averages, not what happened at the worst cycle.

## CPU busy per core

| Series | Tier | n runs | Samples per run | Core 0 % | Core 1 % | Core 2 % | Core 3 % | Whole board % | Core 3 highest 10-s % |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | rnet | 2 | 182–182 | 7.3 [7.3–7.3] | 9.8 [9.6–10.1] | 4.5 [4.3–4.7] | 3.1 [3.0–3.2] | 6.2 [6.2–6.2] | 20.8 |
| A | rdeploy | 2 | 182–182 | 45.0 [35.4–54.5] | 61.4 [42.2–80.6] | 70.8 [45.9–95.6] | 79.3 [71.2–87.3] | 64.1 [63.1–65.1] | 100.0 |
| A | rboth | 2 | 182–182 | 41.6 [40.9–42.4] | 85.6 [75.5–95.6] | 79.6 [74.8–84.3] | 78.5 [69.6–87.4] | 71.3 [70.0–72.6] | 100.0 |
| B | rnet | 2 | 182–182 | 9.1 [8.7–9.4] | 9.9 [9.5–10.4] | 4.3 [3.0–5.6] | 2.9 [2.3–3.6] | 6.6 [6.4–6.7] | 31.9 |
| B | rdeploy | 2 | 182–182 | 37.9 [32.1–43.8] | 55.0 [25.8–84.2] | 98.5 [97.0–99.9] | 63.6 [30.1–97.2] | 63.7 [63.7–63.8] | 100.0 |
| B | rboth | 2 | 182–182 | 40.0 [39.7–40.2] | 82.9 [74.5–91.3] | 77.8 [74.3–81.4] | 84.8 [84.7–84.9] | 71.4 [70.1–72.6] | 100.0 |
| B-iso | rnet | 2 | 182–182 | 8.7 [8.6–8.8] | 8.4 [8.3–8.5] | 1.8 [1.7–1.8] | 0.6 [0.5–0.6] | 4.9 [4.8–4.9] | 7.6 |
| B-iso | rdeploy | 2 | 182–182 | 83.9 [82.1–85.7] | 83.3 [81.0–85.7] | 79.3 [74.8–83.7] | 3.9 [3.8–4.0] | 62.6 [62.5–62.7] | 12.2 |
| B-iso | rboth | 2 | 182–182 | 83.6 [79.6–87.6] | 85.8 [84.4–87.3] | 87.8 [85.6–90.1] | 24.3 [23.4–25.2] | 70.4 [69.4–71.4] | 59.7 |
| C act tuned | rnet | 2 | 14–14 | 18.3 [17.9–18.7] | 14.6 [14.6–14.6] | 10.7 [10.5–10.9] | 9.2 [8.6–9.9] | 13.2 [13.0–13.4] | 14.9 |
| C act tuned | rdeploy | 2 | 14–14 | 86.8 [74.5–99.1] | 34.9 [31.1–38.8] | 98.9 [98.0–99.8] | 38.8 [30.3–47.4] | 64.9 [64.7–65.1] | 100.0 |
| C act tuned | rboth | 2 | 14–14 | 47.0 [44.2–49.9] | 86.2 [80.7–91.7] | 64.5 [62.4–66.5] | 89.7 [84.1–95.2] | 71.8 [71.7–72.0] | 100.0 |

(1) Busy % = 100 × (1 − Δ(idle + iowait) / Δtotal) per core over 10-s windows from `/proc/stat`, logged by the load kit's sampler for the whole run (warm-up included). It counts user, kernel, interrupt and softirq time together; the split by kind of work was not recorded.

(2) Under `rdeploy` and `rboth`, onnxruntime's worker threads spin while waiting (library default, step 39), so cores can show ≈ 100 % busy without doing useful inference work. Busy % shows how occupied a core is, not how much useful work it does.

(3) B-iso pins the control thread to core 3 and moves our load, the sampler and the movable IRQs to cores 0–2; for A, B and C nothing is pinned, so 'core 3' is only a label there.

(4) Config C (`C act tuned`) runs are ≈ 2 min long including start-up, so their means come from ≈ 14 samples against ≈ 180 for the 30-min Linux runs. Config C runs also use the board's default CPU frequency setting (Linux runs: fixed 2.016 GHz) and run the setpoint sender, so their busy % is not directly comparable; the cause of differences was not studied.

**Relative lateness definition:** For Linux runs (`A`, `B`, `B-iso`), relative lateness is `L_rel = L_abs - min(L_abs)` within each run (wake-up floor `floor_us = min(L_abs)` subtracted). For Config C runs, lateness is wake-only (`wake_cyc` @ 160 MHz) relative to each run's best-case cycle using a least-squares fitted period (`analyze_latency.load_run(..., period_mode='fit')`).

**Run length & block comparability:** Linux Phase 6a runs span 180,000 cycles (30 min), while Config C runs span 10,000 cycles. Splitting every run into consecutive 10,000-cycle blocks (`block_wcl_median_us`, `block_wcl_max_us`) places Linux and Config C maxima on the same 10,000-cycle horizon.

**Background CNN workload:** The ONNX 1D-CNN model uses fixed-seed random weights on purpose as realistic background compute/memory/disk load only, not as a bearing-fault classifier.

**CPU governor:** Linux runs lock all cores to `performance` during measurement (`run_benchmark_6r.sh`), whereas Config C runs retain the board default `schedutil` governor.

**C act tuned vs C IPC tuned (DECISIONS.md D12):** `C act tuned` equals tuned IPC plus the 500 Hz D3 PWM write, so its idle (`0`) runs are new Phase 6b runs rather than the Phase 5d `ipc_tuned` baseline. It stands in for `C IPC tuned` under realistic load (`rdeploy`, `rnet`, `rboth`) only if F1 held (otherwise `C IPC tuned` realistic-load runs are reported separately).

**R-both (DECISIONS.md D13):** `rnet` and `rdeploy` at the same time (production + burst), the realistic worst case.

**Repeats of `rboth`:** both repeats ran on 2026-11-18, about 8 min apart (Linux) and 1.5 h apart (`act`); they show within-session spread, not day-to-day variation.

**B-iso isolation:** by affinity only (see Kernel work on CPU 3).
