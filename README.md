# AES-128 Encryption: Two Optimized Approaches

This tiny project explores two distinct, optimized approaches for AES-128 encryption, both leveraging on-the-fly key expansion to enhance efficiency. The two designs are implemented in separate branches: `Iterative` and `Fully_unrolled`.

The core idea is to generate round keys as they are needed, rather than pre-calculating and storing them, which saves significant area and can improve performance under certain architectures.

## Design 1: Fully Unrolled for Maximum Performance

This approach prioritizes raw performance, aiming for the highest possible throughput and Fmax.

-   **Architecture**: The 10 rounds of AES encryption are fully unrolled, meaning each round is a distinct hardware block.
-   **Pipelining**: To further boost the clock frequency, a 2-stage pipeline is implemented within each round.
-   **Branch**: `Fully_unrolled`

### Performance and Resource Utilization

| Metric                | Value                               |
| --------------------- | ----------------------------------- |
| **Fmax**              | ~453.104 MHz                        |
| **Latency**           | 21 cycles (~47.67 ns)               |
| **Throughput**        | ~57.9973 Gbps                       |
| **Total On-Chip Power** | ~2.661 W                            |
| **LUTs**              | 9905                                |
| **Flip-Flops (FF)**   | 5269                                |

## Design 2: Iterative for Balanced Area and Fmax

This design focuses on optimizing Fmax while maintaining a smaller hardware footprint, making it a more area-efficient solution.

-   **Architecture**: An iterative design is used, where a single round hardware block is reused for all 10 rounds.
-   **Pipelining**: It incorporates a 2-stage pipeline per round, carefully designed to avoid pipeline bubbles and maximize efficiency.
-   **Branch**: `Iterative`

### Performance and Resource Utilization

| Metric                | Value                               |
| --------------------- | ----------------------------------- |
| **Fmax**              | ~477.5549 MHz                       |
| **Latency**           | 22 cycles (~48.4 ns)                |
| **Throughput**        | ~5.56 Gbps                          |
| **Total On-Chip Power** | 0.317 W                             |
| **LUTs**              | 1376                                |
| **Flip-Flops (FF)**   | 908                                 |

