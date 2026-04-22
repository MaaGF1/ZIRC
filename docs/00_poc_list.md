<!-- docs/00_poc_list.md -->

# Proof of Concept Lists

This document delineates the specific functionalities encapsulated within the `poc/` directory.

Note: that if these "proofs of concept" are essentially my drafts, it is best not to use these scripts if you do not understand the code and its underlying principles.

## 1. Core Functionalities

1. `poc/reward_gun`: Abridges the acquisition sequence for Guns (i.e., T-Dolls) by circumventing playback animations.
2. `poc/set_frame`:  Enables arbitrary framerate modulation, transcending the binary "Low" (30) and "High" (60) FPS constraints of the native settings.
3. `poc/time_scale`: Implements a better speedhack via the Unity engine, facilitating fluid acceleration with lower power consumption.
4. `poc/turn_end`: Remove transitional phase animations, specifically bypassing faction-specific turn-end sequences (e.g., KCCO, Griffin).
5. `poc/calculator`: A calculator for calculating enemy efficiency (score) in ranking mission, e.g. "Region of Chaos", "Flowers of the End".
6. `poc/f2p`: A script used to farm "convolution kernel"'s mission "Escape on the Möbius Strip EX".
7. `poc/trainer`: Some functions for modifying damage and target collection.

## 2. Note

1. `poc/reward_gun`: 
    - Originally conceived for the "Advanced F2P" in "Convolution Kernel".
    - In "EP.14", although the visual sequence is bypassed, a latency period is still mandatory for server-side synchronization, or something else.
2. `poc/set_frame`: 
    - To revert to default parameters, simply re-access the in-game "Settings" page.
    - **Do not** use with any "speedhack" modifications.
3. `poc/time_scale`:
    - It is imperative to **restrict the multiplier to 3.0x**; exceeding this threshold may trigger kick offline due to the lack of integrated timeout mitigation.
4. `poc/turn_end`:
    - Originally conceived for the "Advanced F2P" in "Convolution Kernel".
    - When used in non-standard campaigns (e.g., tri-faction maps or the Gray Zone), the game will crash.