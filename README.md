# частичные результаты до исправления бага с сохранением на каждом обновлении (видно по save_state)

`Spirit`

```
405386963/40094275858 [14:25:04<32914:53:03, 334.95it/s]
total          : took 51339.87 s (100.00%),  3,192,586 samples,  16080.97 ms / 1000 samples,           62.19 hz
save_state     : took 48618.36 s ( 94.70%),  3,192,586 samples,  15228.52 ms / 1000 samples,           65.67 hz
my-drain       : took  2647.91 s (  5.16%),  3,192,586 samples,  829.39 ms / 1000 samples,        1,205.70 hz
tree_search    : took  2551.19 s (  4.97%),  3,192,586 samples,  799.10 ms / 1000 samples,        1,251.41 hz
create_cluster : took    74.85 s (  0.15%),     32,447 samples,  2306.70 ms / 1000 samples,          433.52 hz
mask           : took    45.47 s (  0.09%),  3,192,586 samples,   14.24 ms / 1000 samples,       70,216.50 hz
cluster_exist  : took     8.22 s (  0.02%),  3,160,139 samples,    2.60 ms / 1000 samples,      384,510.53 hz
get-log-content: took     6.94 s (  0.01%),  3,192,586 samples,    2.17 ms / 1000 samples,      459,892.05 hz
```

`Liberty`

```
5301738399/31704047561 [12:54:37<18022:10:23, 406.94it/s]
total          : took 45677.02 s (100.00%), 40,162,688 samples,  1137.30 ms / 1000 samples,          879.28 hz
save_state     : took 41928.04 s ( 91.79%), 40,162,688 samples,  1043.96 ms / 1000 samples,          957.90 hz
my-drain       : took  3122.51 s (  6.84%), 40,162,688 samples,   77.75 ms / 1000 samples,       12,862.31 hz
tree_search    : took  2758.57 s (  6.04%), 40,162,688 samples,   68.68 ms / 1000 samples,       14,559.23 hz
mask           : took   336.49 s (  0.74%), 40,162,688 samples,    8.38 ms / 1000 samples,      119,358.86 hz
create_cluster : took   142.23 s (  0.31%),     40,459 samples,  3515.33 ms / 1000 samples,          284.47 hz
cluster_exist  : took    84.53 s (  0.19%), 40,122,229 samples,    2.11 ms / 1000 samples,      474,623.29 hz
get-log-content: took    73.17 s (  0.16%), 40,162,688 samples,    1.82 ms / 1000 samples,      548,866.71 hz
```

`Tbird`
```
20178146499/31862496114 [14:25:39<208:31:31, 15564.78it/s]
total          : took 50384.88 s (100.00%), 131,967,417 samples,  381.80 ms / 1000 samples,        2,619.19 hz
save_state     : took 43136.47 s ( 85.61%), 131,967,417 samples,  326.87 ms / 1000 samples,        3,059.30 hz
my-drain       : took  3871.56 s (  7.68%), 131,967,417 samples,   29.34 ms / 1000 samples,       34,086.35 hz
tree_search    : took  2501.50 s (  4.96%), 131,967,417 samples,   18.96 ms / 1000 samples,       52,755.36 hz
mask           : took  1815.12 s (  3.60%), 131,967,417 samples,   13.75 ms / 1000 samples,       72,704.51 hz
cluster_exist  : took   542.09 s (  1.08%), 131,946,387 samples,    4.11 ms / 1000 samples,      243,401.77 hz
get-log-content: took   460.01 s (  0.91%), 131,967,417 samples,    3.49 ms / 1000 samples,      286,880.27 hz
create_cluster : took    24.22 s (  0.05%),     21,030 samples,  1151.80 ms / 1000 samples,          868.20 hz
```

`BGL`

```
743186367/743186367 [03:10<00:00, 4102340.45it/s]
total          : took   132.35 s (100.00%),  4,747,963 samples,   27.87 ms / 1000 samples,       35,875.46 hz
my-drain       : took    56.67 s ( 42.82%),  4,747,963 samples,   11.94 ms / 1000 samples,       83,778.85 hz
mask           : took    28.60 s ( 21.61%),  4,747,963 samples,    6.02 ms / 1000 samples,      166,025.78 hz
tree_search    : took    24.75 s ( 18.70%),  4,747,963 samples,    5.21 ms / 1000 samples,      191,829.45 hz
get-log-content: took    13.48 s ( 10.18%),  4,747,963 samples,    2.84 ms / 1000 samples,      352,324.65 hz
cluster_exist  : took    13.03 s (  9.84%),  4,747,963 samples,    2.74 ms / 1000 samples,      364,444.55 hz
save_state     : took     4.16 s (  3.14%),  4,747,963 samples,    0.88 ms / 1000 samples,    1,141,524.94 hz
```

----------------------
# после

...