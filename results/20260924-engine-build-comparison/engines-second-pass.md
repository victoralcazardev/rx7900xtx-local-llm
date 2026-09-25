### A oficial, runtime 7.2.4, q8/q8
   q8_0             pp512        1010.14 ± 45.02 
   q8_0             tg128           39.66 ± 0.09 
   q8_0    pp512 @ d16384         858.62 ± 14.78 
   q8_0    tg128 @ d16384           37.20 ± 0.09 
### B oficial, runtime ROCm10, q8/q8
### C build ROCm10, runtime 7.2.4, q8/q5_1
   q5_1             pp512         997.78 ± 38.69 
   q5_1             tg128           38.61 ± 0.09 
   q5_1    pp512 @ d16384         849.40 ± 19.11 
   q5_1    tg128 @ d16384           33.79 ± 0.08 
### D build ROCm10, runtime ROCm10, q8/q5_1
FIN
### E build ROCm10 SIN kvmix, q8/q8
           pp512        1010.04 ± 36.12 
           tg128           39.24 ± 0.10 
  pp512 @ d16384         853.03 ± 16.59 
  tg128 @ d16384           36.87 ± 0.08 
### F build ROCm10 CON kvmix, q8/q8
           pp512         994.10 ± 39.32 
           tg128           38.95 ± 0.08 
  pp512 @ d16384         848.78 ± 15.49 
  tg128 @ d16384           36.78 ± 0.11 
