#!/usr/bin/env python3
"""EFHW Fuchs ATU V3.0 — schemdraw 自动化原理图

严格 Netlist 拓扑驱动。两段式错位隔离布局:
  Sheet A (上): POWER + MCU + SERVO_SWITCH
  Sheet B (下): RF_IN → DC_BLOCK → T200-6_FUCHS → PROTECTION → ANTENNA
  Sheet C (底): STAR GROUND

Usage: pip install 'schemdraw>=0.19' && python3 schemdraw_schematic.py
"""

import matplotlib
matplotlib.use('Agg')
import schemdraw
import schemdraw.elements as elm
from schemdraw.elements.intcircuits import IcPin

UNIT = 2.5

with schemdraw.Drawing(unit=UNIT, fontsize=10) as d:
    d.config(margin=0.3, lw=1.8)

    # ═══════════════════════════════════════════════════════════════
    # SHEET A — POWER, MCU, SERVO SWITCH
    # ═══════════════════════════════════════════════════════════════

    # A1: DC INPUT + REVERSE-POLARITY DIODE
    d += elm.Line(arrow='->').label('DC_RAW\n13.8V', 'left')
    d += elm.Diode().label('D1\n1N4007', 'top')

    # A2: LM2940CT-12 LDO
    d += elm.Line().length(0.3)
    LDO12 = d.add(elm.Ic(size=(1.8, 1.2),
        pins=[IcPin(name='IN', side='left', anchorname='in'),
              IcPin(name='GND', side='bottom', anchorname='gnd'),
              IcPin(name='OUT', side='right', anchorname='out')]).label('LM2940\n-12V', 'center'))
    d.push()
    d += elm.Line().down().at(LDO12.gnd).length(0.4)
    d += elm.Ground().label('GND_PCB', 'right')
    d.pop()
    d += elm.Line().length(0.5)
    P_12V = d.here
    d += elm.Dot().label('VCC_12V', 'top')

    # A3: ADC DIVIDER (R1+R2 → GPIO5)
    d.push()
    d += elm.Line().down().length(0.5)
    d += elm.Resistor().label('R1 47kΩ', 'right')
    d += elm.Dot().label('ADC_BIAS_V\n→ GPIO5', 'right')
    d += elm.Resistor().label('R2 10kΩ', 'right')
    d += elm.Ground()
    d.pop()

    # A4: LM2596 12V→6V BUCK
    d += elm.Line().right().length(1.2)
    BUCK = d.add(elm.Ic(size=(1.8, 1.2),
        pins=[IcPin(name='IN', side='left', anchorname='in'),
              IcPin(name='GND', side='bottom', anchorname='gnd'),
              IcPin(name='OUT', side='right', anchorname='out')]).label('LM2596\n-6V Buck', 'center'))
    d += elm.Line().length(0.5)
    P_6V = d.here
    d += elm.Dot().label('VCC_6V', 'top')

    # A5: AMS1117 12V→3.3V LDO (vertical branch up from 12V rail)
    d.push()
    d += elm.Line().up().at(P_12V).length(2.5)
    d += elm.Line().right().length(1.2)
    LDO33 = d.add(elm.Ic(size=(1.8, 1.2),
        pins=[IcPin(name='IN', side='left', anchorname='in'),
              IcPin(name='GND', side='bottom', anchorname='gnd'),
              IcPin(name='OUT', side='right', anchorname='out')]).label('AMS1117\n-3.3V LDO', 'center'))
    d += elm.Line().length(0.5)
    P_3V3 = d.here
    d += elm.Dot().label('VCC_3V3', 'top')
    d.pop()

    # A6: ESP32-S3 MCU (under 3V3 rail)
    d += elm.Line().right().at(P_3V3).length(2.0)
    d += elm.Line().down().length(0.6)
    MCU = d.add(elm.Ic(size=(2.4, 2.2),
        pins=[IcPin(name='3.3V', side='left', anchorname='p3v3'),
              IcPin(name='GPIO5', side='left', anchorname='gpio5'),
              IcPin(name='GPIO2', side='right', anchorname='gpio2'),
              IcPin(name='GPIO1', side='right', anchorname='gpio1'),
              IcPin(name='GND', side='bottom', anchorname='gnd')]).label('ESP32-S3\nWROOM-1', 'center'))
    d.push()
    d += elm.Line().down().at(MCU.gnd).length(0.3)
    d += elm.Ground()
    d.pop()

    # A7: SERVO P-MOSFET POWER SWITCH
    # GPIO2 → R3 → Q2(NPN) → Q1(PFET gate)
    d += elm.Line().right().at(MCU.gpio2).length(0.8)
    d += elm.Resistor().label('R3 1kΩ', 'top')
    Q2 = d.add(elm.BjtNpn().label('Q2\n2N2222A', 'right'))
    d.push()
    d += elm.Line().down().at(Q2.emitter).length(0.3)
    d += elm.Ground()
    d.pop()

    d += elm.Line().right().length(0.5)

    # P-MOSFET high-side switch
    Q1 = d.add(elm.PFet().anchor('source').label('Q1\nIRF9540', 'left').right())

    # Gate pull-up R4 → 6V rail
    d.push()
    d += elm.Line().up().at(Q1.gate).length(0.5)
    d += elm.Line().left().length(0.5)
    d += elm.Resistor().label('R4\n10kΩ', 'left').left()
    d += elm.Line().up().length(1.4)
    d += elm.Line().left().tox(P_6V)
    d += elm.Dot()
    d.pop()

    # 6V→Q1 source supply
    d.push()
    d += elm.Line().up().at(Q1.source).length(1.4)
    d += elm.Line().left().tox(P_6V)
    d += elm.Dot()
    d.pop()

    # Drain → VCC_SERVO
    d += elm.Line().right().at(Q1.drain).length(0.5)
    d += elm.Dot().label('VCC_SERVO', 'top')
    d += elm.Line().right().length(0.5)

    # A8: SERVO HEADER
    d += elm.Ic(size=(1.2, 1.8),
        pins=[IcPin(name='1:GND', side='left', anchorname='sgnd'),
              IcPin(name='2:VCC', side='left', anchorname='svcc'),
              IcPin(name='3:PWM', side='left', anchorname='spwm')]).label('SERVO\nHDR', 'center')

    # ═══════════════════════════════════════════════════════════════
    # SHEET B — HIGH-VOLTAGE RF RESONANT TANK
    # ═══════════════════════════════════════════════════════════════
    d.move(dx=-32, dy=-10)

    # B1: RF INPUT
    d += elm.Line(arrow='->').label('RF_IN\n(50Ω)', 'left')

    # B2: DC-BLOCK CAPACITORS
    d += elm.Capacitor().label('C_block\n10nF 1kV\n×2 C0G', 'top')
    d += elm.Line().length(0.3)
    P_RF = d.here
    d += elm.Dot()

    # B3: T200-6 PRIMARY — 2T shunt inductor to GND
    d.push()
    d += elm.Inductor2().down().label('Primary\n2T', 'right')
    d += elm.Line().down().length(0.2)
    d += elm.Ground()
    d.pop()

    # B4: T200-6 SECONDARY — 14T (AC-coupled via magnetic core)
    d += elm.Line().right().length(2.2)
    P_SEC = d.here
    d += elm.Inductor2().down().label('Secondary\n14T', 'right')
    d += elm.Line().down().length(0.2)
    d += elm.Ground()

    # B5: AIR VARIABLE CAPACITOR — parallel with secondary (Fuchs topology)
    d.push()
    d += elm.Line().right().at(P_SEC).length(1.2)
    d += elm.CapacitorVar().down().label('Air Var Cap\n10-500pF\n≥1kV', 'right')
    d += elm.Line().down().length(0.2)
    d += elm.Ground()
    d.pop()

    # B6: OUTPUT PROTECTION
    d += elm.Line().right().at(P_SEC).length(3.0)
    P_ANT = d.here
    d += elm.Dot()

    # 2.2MΩ bleeder to chassis ground
    d.push()
    d += elm.Resistor().down().at(P_ANT).label('R_bleed\n2.2MΩ\n2W 3KV', 'right')
    d += elm.Ground().label('CHASSIS', 'right')
    d.pop()

    # B7: ANTENNA TERMINAL
    d += elm.Line().right().length(0.6)
    d += elm.Line(arrow='->').length(0.4).label('ANTENNA\n~20m Wire', 'right')

    # ═══════════════════════════════════════════════════════════════
    # SHEET C — STAR GROUND SYSTEM
    # ═══════════════════════════════════════════════════════════════
    d.move(dx=-9, dy=-5)
    d += elm.Dot(radius=0.2).label('★  STAR\nGROUND', 'top')
    d.push()
    d += elm.Line().left().length(1.8).label('GND_PCB', 'left')
    d.pop()
    d.push()
    d += elm.Line().right().length(1.8).label('GND_ANT', 'right')
    d.pop()
    d += elm.Line().down().length(0.5)
    d += elm.Ground().label('GND_CHASSIS\n(Aluminum Box)', 'right')

out = 'EFHW_Fuchs_ATU_V3_Schematic.png'
d.save(out, dpi=300)
print(f"✅ Schematic saved: {out}")
