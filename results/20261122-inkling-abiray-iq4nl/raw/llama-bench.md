| model                          |       size |     params | backend    | ngl | n_ubatch | type_k | type_v |  fa |            test |                  t/s |
|---|---|---|---|---|---|---|---|---|---|---|
| inkling2_loop ?B IQ4_NL - 4.5 bpw |  13.89 GiB |    26.07 B | ROCm       |  99 |      256 |   q8_0 |   q8_0 |   1 |          pp4096 |       1704.38 ± 0.00 |
| inkling2_loop ?B IQ4_NL - 4.5 bpw |  13.89 GiB |    26.07 B | ROCm       |  99 |      256 |   q8_0 |   q8_0 |   1 |           tg128 |         61.14 ± 0.00 |
| inkling2_loop ?B IQ4_NL - 4.5 bpw |  13.89 GiB |    26.07 B | ROCm       |  99 |      256 |   q8_0 |   q8_0 |   1 | pp4096 @ d65536 |        909.40 ± 0.00 |
| inkling2_loop ?B IQ4_NL - 4.5 bpw |  13.89 GiB |    26.07 B | ROCm       |  99 |      256 |   q8_0 |   q8_0 |   1 |  tg128 @ d65536 |         52.08 ± 0.00 |
| inkling2_loop ?B IQ4_NL - 4.5 bpw |  13.89 GiB |    26.07 B | ROCm       |  99 |      256 |   q8_0 |   q8_0 |   1 | pp4096 @ d196608 |        439.25 ± 0.00 |
| inkling2_loop ?B IQ4_NL - 4.5 bpw |  13.89 GiB |    26.07 B | ROCm       |  99 |      256 |   q8_0 |   q8_0 |   1 | tg128 @ d196608 |         43.08 ± 0.00 |
build: cb0e46960 (12606)
