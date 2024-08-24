import copy
import logging
import pathlib
import rapidjson
import numpy as np
import talib.abstract as ta
import pandas as pd
import pandas_ta as pta
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import merge_informative_pair
from pandas import DataFrame, Series
from functools import reduce
from freqtrade.persistence import Trade
from datetime import datetime, timedelta
import time
from typing import Optional
import warnings

log = logging.getLogger(__name__)
# log.setLevel(logging.DEBUG)
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

#############################################################################################################
##                NostalgiaForInfinityX5 by iterativ                                                       ##
##           https://github.com/iterativv/NostalgiaForInfinity                                             ##
##                                                                                                         ##
##    Strategy for Freqtrade https://github.com/freqtrade/freqtrade                                        ##
##                                                                                                         ##
#############################################################################################################
##               GENERAL RECOMMENDATIONS                                                                   ##
##                                                                                                         ##
##   For optimal performance, suggested to use between 4 and 6 open trades, with unlimited stake.          ##
##   A pairlist with 40 to 80 pairs. Volume pairlist works well.                                           ##
##   Prefer stable coin (USDT, BUSDT etc) pairs, instead of BTC or ETH pairs.                              ##
##   Highly recommended to blacklist leveraged tokens (*BULL, *BEAR, *UP, *DOWN etc).                      ##
##   Ensure that you don't override any variables in you config.json. Especially                           ##
##   the timeframe (must be 5m).                                                                           ##
##     use_exit_signal must set to true (or not set at all).                                               ##
##     exit_profit_only must set to false (or not set at all).                                             ##
##     ignore_roi_if_entry_signal must set to true (or not set at all).                                    ##
##                                                                                                         ##
#############################################################################################################
##               DONATIONS                                                                                 ##
##                                                                                                         ##
##   BTC: bc1qvflsvddkmxh7eqhc4jyu5z5k6xcw3ay8jl49sk                                                       ##
##   ETH (ERC20): 0x83D3cFb8001BDC5d2211cBeBB8cB3461E5f7Ec91                                               ##
##   BEP20/BSC (USDT, ETH, BNB, ...): 0x86A0B21a20b39d16424B7c8003E4A7e12d78ABEe                           ##
##   TRC20/TRON (USDT, TRON, ...): TTAa9MX6zMLXNgWMhg7tkNormVHWCoq8Xk                                      ##
##                                                                                                         ##
##               REFERRAL LINKS                                                                            ##
##                                                                                                         ##
##  Binance: https://accounts.binance.com/en/register?ref=C68K26A9 (20% discount on trading fees)          ##
##  Kucoin: https://www.kucoin.com/r/af/QBSSS5J2 (20% lifetime discount on trading fees)                   ##
##  Gate.io: https://www.gate.io/signup/UAARUlhf/20pct?ref_type=103 (20% lifetime discount on trading fees)##
##  OKX: https://www.okx.com/join/11749725931 (20% discount on trading fees)                               ##
##  MEXC: https://promote.mexc.com/a/nfi  (10% discount on trading fees)                                   ##
##  ByBit: https://partner.bybit.com/b/nfi                                                                 ##
##  Bitget: https://bonus.bitget.com/nfi (lifetime 20% rebate all & 10% discount on spot fees)             ##
##  HTX: https://www.htx.com/invite/en-us/1f?invite_code=ubpt2223                                          ##
##         (Welcome Bonus worth 241 USDT upon completion of a deposit and trade)                           ##
##  Bitvavo: https://account.bitvavo.com/create?a=D22103A4BC (no fees for the first € 1000)                ##
#############################################################################################################


class NostalgiaForInfinityX5(IStrategy):
  INTERFACE_VERSION = 3

  def version(self) -> str:
    return "v15.0.30"

  stoploss = -0.99

  # Trailing stoploss (not used)
  trailing_stop = False
  trailing_only_offset_is_reached = True
  trailing_stop_positive = 0.01
  trailing_stop_positive_offset = 0.03

  use_custom_stoploss = False

  # Optimal timeframe for the strategy.
  timeframe = "5m"
  info_timeframes = ["15m", "1h", "4h", "1d"]

  # BTC informatives
  btc_info_timeframes = ["5m", "15m", "1h", "4h", "1d"]

  # Backtest Age Filter emulation
  has_bt_agefilter = False
  bt_min_age_days = 3

  # Exchange Downtime protection
  has_downtime_protection = False

  # Do you want to use the hold feature? (with hold-trades.json)
  hold_support_enabled = True

  # Run "populate_indicators()" only for new candle.
  process_only_new_candles = True

  # These values can be overridden in the "ask_strategy" section in the config.
  use_exit_signal = True
  exit_profit_only = False
  ignore_roi_if_entry_signal = True

  # Number of candles the strategy requires before producing valid signals
  startup_candle_count: int = 800

  # Number of cores to use for pandas_ta indicators calculations
  num_cores_indicators_calc = 0

  # Long Normal mode tags
  long_normal_mode_tags = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
  # Long Pump mode tags
  long_pump_mode_tags = ["21", "22", "23", "24", "25", "26"]
  # Long Quick mode tags
  long_quick_mode_tags = ["41", "42", "43", "44", "45", "46", "47", "48", "49", "50", "51", "52", "53"]
  # Long rebuy mode tags
  long_rebuy_mode_tags = ["61", "62"]
  # Long high profit mode tags
  long_mode_tags = ["81", "82"]
  # Long rapid mode tags
  long_rapid_mode_tags = ["101", "102", "103", "104", "105", "106", "107", "108", "109", "110"]
  # Long grind mode tags
  long_grind_mode_tags = ["120"]

  long_normal_mode_name = "long_normal"
  long_pump_mode_name = "long_pump"
  long_quick_mode_name = "long_quick"
  long_rebuy_mode_name = "long_rebuy"
  long_high_profit_mode_name = "long_hp"
  long_rapid_mode_name = "long_rapid"
  long_grind_mode_name = "long_grind"

  # Shorting

  # Short normal mode tags
  short_normal_mode_tags = ["500", "501"]
  # Short Pump mode tags
  short_pump_mode_tags = ["521", "522", "523", "524", "525", "526"]
  # Short Quick mode tags
  short_quick_mode_tags = ["541", "542", "543", "544", "545", "546", "547", "548", "549", "550"]
  # Short rebuy mode tags
  short_rebuy_mode_tags = ["561"]
  # Short mode tags
  short_mode_tags = ["581", "582"]
  # Short rapid mode tags
  short_rapid_mode_tags = ["601", "602", "603", "604", "605", "606", "607", "608", "609", "610"]
  # Short grind mode tags
  short_grind_mode_tags = ["620"]

  short_normal_mode_name = "short_normal"
  short_pump_mode_name = "short_pump"
  short_quick_mode_name = "short_quick"
  short_rebuy_mode_name = "short_rebuy"
  short_high_profit_mode_name = "short_hp"
  short_rapid_mode_name = "short_rapid"

  is_futures_mode = False
  futures_mode_leverage = 3.0
  futures_mode_leverage_rebuy_mode = 3.0
  futures_mode_leverage_grind_mode = 3.0

  # Based on the the first entry (regardless of rebuys)
  stop_threshold_spot = 0.10
  stop_threshold_futures = 0.10
  stop_threshold_doom_spot = 0.25
  stop_threshold_doom_futures = 0.25
  stop_threshold_rapid_spot = 0.25
  stop_threshold_rapid_futures = 0.25
  stop_threshold_spot_rebuy = 1.0
  stop_threshold_futures_rebuy = 1.0

  # user specified fees to be used for profit calculations
  custom_fee_open_rate = None
  custom_fee_close_rate = None

  # Rebuy mode minimum number of free slots
  rebuy_mode_min_free_slots = 2

  # Position adjust feature
  position_adjustment_enable = True

  # Grinding feature
  grinding_enable = True

  # Grinding
  grind_1_stop_grinds_spot = -0.03
  grind_1_profit_threshold_spot = 0.018
  grind_1_stakes_spot = [0.22, 0.24, 0.26]
  grind_1_sub_thresholds_spot = [-0.065, -0.075, -0.085]

  grind_1_stop_grinds_futures = -0.03
  grind_1_profit_threshold_futures = 0.018
  grind_1_stakes_futures = [0.22, 0.24, 0.26]
  grind_1_sub_thresholds_futures = [-0.065, -0.075, -0.085]

  grind_2_stop_grinds_spot = -0.03
  grind_2_profit_threshold_spot = 0.018
  grind_2_stakes_spot = [0.16, 0.26, 0.32]
  grind_2_sub_thresholds_spot = [-0.065, -0.075, -0.085]

  grind_2_stop_grinds_futures = -0.03
  grind_2_profit_threshold_futures = 0.018
  grind_2_stakes_futures = [0.16, 0.26, 0.32]
  grind_2_sub_thresholds_futures = [-0.065, -0.075, -0.085]

  grind_3_stop_grinds_spot = -0.03
  grind_3_profit_threshold_spot = 0.018
  grind_3_stakes_spot = [0.16, 0.18, 0.20]
  grind_3_sub_thresholds_spot = [-0.065, -0.075, -0.085]

  grind_3_stop_grinds_futures = -0.03
  grind_3_profit_threshold_futures = 0.018
  grind_3_stakes_futures = [0.16, 0.18, 0.20]
  grind_3_sub_thresholds_futures = [-0.065, -0.075, -0.085]

  grind_4_stop_grinds_spot = -0.03
  grind_4_profit_threshold_spot = 0.018
  grind_4_stakes_spot = [0.16, 0.18, 0.20]
  grind_4_sub_thresholds_spot = [-0.065, -0.075, -0.085]

  grind_4_stop_grinds_futures = -0.03
  grind_4_profit_threshold_futures = 0.018
  grind_4_stakes_futures = [0.16, 0.18, 0.20]
  grind_4_sub_thresholds_futures = [-0.065, -0.075, -0.085]

  grind_5_stop_grinds_spot = -0.03
  grind_5_profit_threshold_spot = 0.048
  grind_5_stakes_spot = [0.16, 0.18, 0.20]
  grind_5_sub_thresholds_spot = [-0.065, -0.075, -0.085]

  grind_5_stop_grinds_futures = -0.03
  grind_5_profit_threshold_futures = 0.048
  grind_5_stakes_futures = [0.16, 0.18, 0.20]
  grind_5_sub_thresholds_futures = [-0.065, -0.075, -0.085]

  grind_6_stop_grinds_spot = -0.03
  grind_6_profit_threshold_spot = 0.018
  grind_6_stakes_spot = [0.05, 0.057, 0.065, 0.074, 0.084, 0.095, 0.107, 0.121, 0.137]
  grind_6_sub_thresholds_spot = [-0.03, -0.035, -0.04, -0.045, -0.05, -0.055, -0.06, -0.065, -0.07]

  grind_6_stop_grinds_futures = -0.03
  grind_6_profit_threshold_futures = 0.018
  grind_6_stakes_futures = [0.05, 0.057, 0.065, 0.074, 0.084, 0.095, 0.107, 0.121, 0.137]
  grind_6_sub_thresholds_futures = [-0.03, -0.035, -0.04, -0.045, -0.05, -0.055, -0.06, -0.065, -0.07]

  grind_1_derisk_1_stop_grinds_spot = -0.03
  grind_1_derisk_1_profit_threshold_spot = 0.018
  grind_1_derisk_1_stakes_spot = [0.25, 0.30, 0.35]
  grind_1_derisk_1_sub_thresholds_spot = [-0.07, -0.08, -0.09]

  grind_1_derisk_1_stop_grinds_futures = -0.03
  grind_1_derisk_1_profit_threshold_futures = 0.018
  grind_1_derisk_1_stakes_futures = [0.25, 0.30, 0.35]
  grind_1_derisk_1_sub_thresholds_futures = [-0.07, -0.08, -0.09]

  grind_2_derisk_1_stop_grinds_spot = -0.03
  grind_2_derisk_1_profit_threshold_spot = 0.018
  grind_2_derisk_1_stakes_spot = [0.16, 0.22, 0.28]
  grind_2_derisk_1_sub_thresholds_spot = [-0.065, -0.075, -0.085]

  grind_2_derisk_1_stop_grinds_futures = -0.03
  grind_2_derisk_1_profit_threshold_futures = 0.018
  grind_2_derisk_1_stakes_futures = [0.16, 0.22, 0.28]
  grind_2_derisk_1_sub_thresholds_futures = [-0.065, -0.075, -0.085]

  grinds_stop_spot = -0.12
  grinds_stop_futures = -0.12

  # Non rebuy modes
  regular_mode_stake_multiplier_spot = [1.0]
  regular_mode_stake_multiplier_futures = [1.0]
  regular_mode_use_grind_stops = False

  regular_mode_rebuy_stakes_spot = [0.10, 0.10, 0.10]
  regular_mode_rebuy_thresholds_spot = [-0.12, -0.14, -0.16]
  regular_mode_grind_1_stakes_spot = [0.22, 0.24, 0.26]
  regular_mode_grind_1_thresholds_spot = [-0.06, -0.07, -0.09]
  regular_mode_grind_1_stop_grinds_spot = -0.20
  regular_mode_grind_1_profit_threshold_spot = 0.018
  regular_mode_grind_2_stakes_spot = [0.14, 0.20, 0.26]
  regular_mode_grind_2_thresholds_spot = [-0.04, -0.06, -0.08]
  regular_mode_grind_2_stop_grinds_spot = -0.20
  regular_mode_grind_2_profit_threshold_spot = 0.018
  regular_mode_grind_3_stakes_spot = [0.18, 0.20, 0.22]
  regular_mode_grind_3_thresholds_spot = [-0.03, -0.06, -0.08]
  regular_mode_grind_3_stop_grinds_spot = -0.20
  regular_mode_grind_3_profit_threshold_spot = 0.018
  regular_mode_grind_4_stakes_spot = [0.18, 0.20, 0.22]
  regular_mode_grind_4_thresholds_spot = [-0.03, -0.06, -0.08]
  regular_mode_grind_4_stop_grinds_spot = -0.20
  regular_mode_grind_4_profit_threshold_spot = 0.018
  regular_mode_grind_5_stakes_spot = [0.18, 0.20, 0.22]
  regular_mode_grind_5_thresholds_spot = [-0.03, -0.06, -0.08]
  regular_mode_grind_5_stop_grinds_spot = -0.20
  regular_mode_grind_5_profit_threshold_spot = 0.048
  regular_mode_grind_6_stakes_spot = [0.05, 0.057, 0.065, 0.074, 0.084, 0.095, 0.107, 0.121, 0.137]
  regular_mode_grind_6_thresholds_spot = [-0.025, -0.03, -0.035, -0.04, -0.045, -0.05, -0.055, -0.06, -0.065]
  regular_mode_grind_6_stop_grinds_spot = -0.20
  regular_mode_grind_6_profit_threshold_spot = 0.018
  regular_mode_derisk_1_spot = -0.40
  regular_mode_derisk_1_spot_old = -0.80
  regular_mode_derisk_1_reentry_spot = -0.08
  regular_mode_derisk_spot = -0.40
  regular_mode_derisk_spot_old = -1.60

  regular_mode_rebuy_stakes_futures = [0.10, 0.10, 0.10]
  regular_mode_rebuy_thresholds_futures = [-0.12, -0.14, -0.16]
  regular_mode_grind_1_stakes_futures = [0.22, 0.24, 0.26]
  regular_mode_grind_1_thresholds_futures = [-0.06, -0.07, -0.09]
  regular_mode_grind_1_stop_grinds_futures = -0.20
  regular_mode_grind_1_profit_threshold_futures = 0.018
  regular_mode_grind_2_stakes_futures = [0.14, 0.20, 0.26]
  regular_mode_grind_2_thresholds_futures = [-0.04, -0.06, -0.08]
  regular_mode_grind_2_stop_grinds_futures = -0.20
  regular_mode_grind_2_profit_threshold_futures = 0.018
  regular_mode_grind_3_stakes_futures = [0.18, 0.20, 0.22]
  regular_mode_grind_3_thresholds_futures = [-0.03, -0.06, -0.08]
  regular_mode_grind_3_stop_grinds_futures = -0.20
  regular_mode_grind_3_profit_threshold_futures = 0.018
  regular_mode_grind_4_stakes_futures = [0.18, 0.20, 0.22]
  regular_mode_grind_4_thresholds_futures = [-0.03, -0.06, -0.08]
  regular_mode_grind_4_stop_grinds_futures = -0.20
  regular_mode_grind_4_profit_threshold_futures = 0.018
  regular_mode_grind_5_stakes_futures = [0.18, 0.20, 0.22]
  regular_mode_grind_5_thresholds_futures = [-0.03, -0.06, -0.08]
  regular_mode_grind_5_stop_grinds_futures = -0.20
  regular_mode_grind_5_profit_threshold_futures = 0.048
  regular_mode_grind_6_stakes_futures = [0.05, 0.057, 0.065, 0.074, 0.084, 0.095, 0.107, 0.121, 0.137]
  regular_mode_grind_6_thresholds_futures = [-0.025, -0.03, -0.035, -0.04, -0.045, -0.05, -0.055, -0.06, -0.065]
  regular_mode_grind_6_stop_grinds_futures = -0.20
  regular_mode_grind_6_profit_threshold_futures = 0.018
  regular_mode_derisk_1_futures = -0.40
  regular_mode_derisk_1_futures_old = -0.80
  regular_mode_derisk_1_reentry_futures = -0.08  # without leverage
  regular_mode_derisk_futures = -0.40
  regular_mode_derisk_futures_old = -1.20

  # Rebuy mode
  rebuy_mode_stake_multiplier = 0.2
  # rebuy_mode_stake_multiplier_alt = 0.3
  # rebuy_mode_max = 3
  rebuy_mode_derisk_spot = -1.0
  rebuy_mode_derisk_futures = -2.0
  rebuy_mode_stakes_spot = [1.0, 1.25, 1.5, 1.75, 2.0]
  rebuy_mode_stakes_futures = [1.0, 1.25, 1.5, 1.75, 2.0]
  rebuy_mode_thresholds_spot = [-0.04, -0.06, -0.08, -0.10, -0.12]
  rebuy_mode_thresholds_futures = [-0.04, -0.06, -0.08, -0.10, -0.12]

  # Grind mode
  grind_mode_stake_multiplier_spot = [0.20, 0.30, 0.40, 0.50, 0.60, 0.70]
  grind_mode_stake_multiplier_futures = [0.20, 0.30, 0.40, 0.50]
  grind_mode_first_entry_profit_threshold_spot = 0.018
  grind_mode_first_entry_profit_threshold_futures = 0.018
  grind_mode_first_entry_stop_threshold_spot = -0.20
  grind_mode_first_entry_stop_threshold_futures = -0.20
  grind_mode_max_slots = 1
  grind_mode_coins = [
    "MATIC",
    "ADA",
    "ARB",
    "DOT",
    "XLM",
    "ALGO",
    "ETH",
    "RNDR",
    "XMR",
    "AVAX",
    "NEAR",
    "DOGE",
    "BCH",
    "ETC",
    "FTM",
    "KAS",
    "HBAR",
    "SUI",
    "TON",
    "XRP",
    "UNI",
    "LTC",
    "FIL",
    "ATOM",
    "GRT",
    "LINK",
    "VET",
    "THETA",
    "EOS",
    "LRC",
    "QTUM",
    "CELR",
  ]

  # Profit max thresholds
  profit_max_thresholds = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.05, 0.05]

  # Max allowed buy "slippage", how high to buy on the candle
  max_slippage = 0.012

  # BTC/ETH stakes
  btc_stakes = ["BTC", "ETH"]

  #############################################################
  # Buy side configuration

  long_entry_signal_params = {
    # Enable/Disable conditions
    # -------------------------------------------------------
    "long_entry_condition_1_enable": True,
    "long_entry_condition_2_enable": True,
    "long_entry_condition_3_enable": True,
    "long_entry_condition_41_enable": True,
    "long_entry_condition_42_enable": True,
    "long_entry_condition_43_enable": True,
    "long_entry_condition_120_enable": True,
  }

  short_entry_signal_params = {
    # Enable/Disable conditions
    # -------------------------------------------------------
    # "short_entry_condition_500_enable": False,
    "short_entry_condition_501_enable": False,
  }

  #############################################################
  # CACHES

  hold_trades_cache = None
  target_profit_cache = None
  #############################################################
  #
  #
  #  $$$$$$\   $$$$$$\  $$\      $$\ $$\      $$\  $$$$$$\  $$\   $$\
  # $$  __$$\ $$  __$$\ $$$\    $$$ |$$$\    $$$ |$$  __$$\ $$$\  $$ |
  # $$ /  \__|$$ /  $$ |$$$$\  $$$$ |$$$$\  $$$$ |$$ /  $$ |$$$$\ $$ |
  # $$ |      $$ |  $$ |$$\$$\$$ $$ |$$\$$\$$ $$ |$$ |  $$ |$$ $$\$$ |
  # $$ |      $$ |  $$ |$$ \$$$  $$ |$$ \$$$  $$ |$$ |  $$ |$$ \$$$$ |
  # $$ |  $$\ $$ |  $$ |$$ |\$  /$$ |$$ |\$  /$$ |$$ |  $$ |$$ |\$$$ |
  # \$$$$$$  | $$$$$$  |$$ | \_/ $$ |$$ | \_/ $$ | $$$$$$  |$$ | \$$ |
  #  \______/  \______/ \__|     \__|\__|     \__| \______/ \__|  \__|
  #
  #
  #
  # $$$$$$$$\ $$\   $$\ $$\   $$\  $$$$$$\ $$$$$$$$\ $$$$$$\  $$$$$$\  $$\   $$\  $$$$$$\
  # $$  _____|$$ |  $$ |$$$\  $$ |$$  __$$\\__$$  __|\_$$  _|$$  __$$\ $$$\  $$ |$$  __$$\
  # $$ |      $$ |  $$ |$$$$\ $$ |$$ /  \__|  $$ |     $$ |  $$ /  $$ |$$$$\ $$ |$$ /  \__|
  # $$$$$\    $$ |  $$ |$$ $$\$$ |$$ |        $$ |     $$ |  $$ |  $$ |$$ $$\$$ |\$$$$$$\
  # $$  __|   $$ |  $$ |$$ \$$$$ |$$ |        $$ |     $$ |  $$ |  $$ |$$ \$$$$ | \____$$\
  # $$ |      $$ |  $$ |$$ |\$$$ |$$ |  $$\   $$ |     $$ |  $$ |  $$ |$$ |\$$$ |$$\   $$ |
  # $$ |      \$$$$$$  |$$ | \$$ |\$$$$$$  |  $$ |   $$$$$$\  $$$$$$  |$$ | \$$ |\$$$$$$  |
  # \__|       \______/ \__|  \__| \______/   \__|   \______| \______/ \__|  \__| \______/
  #
  #

  ###############################################################################################
  # COMMON FUNCTIONS FOR BOTH LONG AND SHORT SIDE STARTS HERE
  ###############################################################################################

  def __init__(self, config: dict) -> None:
    if "ccxt_config" not in config["exchange"]:
      config["exchange"]["ccxt_config"] = {}
    if "ccxt_async_config" not in config["exchange"]:
      config["exchange"]["ccxt_async_config"] = {}

    options = {
      "brokerId": None,
      "broker": {"spot": None, "margin": None, "future": None, "delivery": None},
      "partner": {
        "spot": {"id": None, "key": None},
        "future": {"id": None, "key": None},
        "id": None,
        "key": None,
      },
    }

    config["exchange"]["ccxt_config"]["options"] = options
    config["exchange"]["ccxt_async_config"]["options"] = options
    super().__init__(config)
    if ("exit_profit_only" in self.config and self.config["exit_profit_only"]) or (
      "sell_profit_only" in self.config and self.config["sell_profit_only"]
    ):
      self.exit_profit_only = True
    if "num_cores_indicators_calc" in self.config:
      self.num_cores_indicators_calc = self.config["num_cores_indicators_calc"]

    if "custom_fee_open_rate" in self.config:
      self.custom_fee_open_rate = self.config["custom_fee_open_rate"]
    if "custom_fee_close_rate" in self.config:
      self.custom_fee_close_rate = self.config["custom_fee_close_rate"]

    if "futures_mode_leverage" in self.config:
      self.futures_mode_leverage = self.config["futures_mode_leverage"]
    if "futures_mode_leverage_rebuy_mode" in self.config:
      self.futures_mode_leverage_rebuy_mode = self.config["futures_mode_leverage_rebuy_mode"]
    if "futures_mode_leverage_grind_mode" in self.config:
      self.futures_mode_leverage_grind_mode = self.config["futures_mode_leverage_grind_mode"]

    if "grind_mode_max_slots" in self.config:
      self.grind_mode_max_slots = self.config["grind_mode_max_slots"]
    if "grind_mode_coins" in self.config:
      self.grind_mode_coins = self.config["grind_mode_coins"]
    if "max_slippage" in self.config:
      self.max_slippage = self.config["max_slippage"]
    if self.target_profit_cache is None:
      bot_name = ""
      if "bot_name" in self.config:
        bot_name = self.config["bot_name"] + "-"
      self.target_profit_cache = Cache(
        self.config["user_data_dir"]
        / (
          "nfix5-profit_max-"
          + bot_name
          + self.config["exchange"]["name"]
          + "-"
          + self.config["stake_currency"]
          + ("-(backtest)" if (self.config["runmode"].value == "backtest") else "")
          + ("-(hyperopt)" if (self.config["runmode"].value == "hyperopt") else "")
          + ".json"
        )
      )

    # OKX, Kraken provides a lower number of candle data per API call
    if self.config["exchange"]["name"] in ["okx", "okex"]:
      self.startup_candle_count = 480
    elif self.config["exchange"]["name"] in ["kraken"]:
      self.startup_candle_count = 710
    elif self.config["exchange"]["name"] in ["bybit"]:
      self.startup_candle_count = 199
    elif self.config["exchange"]["name"] in ["bitget"]:
      self.startup_candle_count = 499
    elif self.config["exchange"]["name"] in ["bingx"]:
      self.startup_candle_count = 499

    if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
      self.is_futures_mode = True
      self.can_short = True

    # If the cached data hasn't changed, it's a no-op
    self.target_profit_cache.save()

  # Get Ticker Indicator
  # ---------------------------------------------------------------------------------------------
  def get_ticker_indicator(self):
    return int(self.timeframe[:-1])

  # Mark Profit Target
  # ---------------------------------------------------------------------------------------------
  def mark_profit_target(
    self,
    mode_name: str,
    pair: str,
    sell: bool,
    signal_name: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    last_candle,
    previous_candle_1,
  ) -> tuple:
    if sell and (signal_name is not None):
      return pair, signal_name

    return None, None

  # Exit Profit Target
  # ---------------------------------------------------------------------------------------------
  def exit_profit_target(
    self,
    mode_name: str,
    pair: str,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    last_candle,
    previous_candle_1,
    previous_rate,
    previous_profit,
    previous_sell_reason,
    previous_time_profit_reached,
    enter_tags,
  ) -> tuple:
    if previous_sell_reason in [f"exit_{mode_name}_stoploss_doom", f"exit_{mode_name}_stoploss"]:
      if profit_ratio > 0.04:
        # profit is over the threshold, don't exit
        self._remove_profit_target(pair)
        return False, None
      if profit_ratio < -0.18:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
      elif profit_ratio < -0.1:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
      elif profit_ratio < -0.04:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
      else:
        if profit_ratio < (previous_profit - 0.04):
          return True, previous_sell_reason
    elif previous_sell_reason in [f"exit_{mode_name}_stoploss_u_e"]:
      if profit_current_stake_ratio > 0.04:
        # profit is over the threshold, don't exit
        self._remove_profit_target(pair)
        return False, None
      if profit_ratio < (previous_profit - (0.20 if trade.realized_profit == 0.0 else 0.26)):
        return True, previous_sell_reason
    elif previous_sell_reason in [f"exit_profit_{mode_name}_max"]:
      if profit_init_ratio < -0.08:
        # profit is under the threshold, cancel it
        self._remove_profit_target(pair)
        return False, None
      if trade.is_short:
        if 0.001 <= profit_init_ratio < 0.01:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_0_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_0_2"
        elif 0.01 <= profit_init_ratio < 0.02:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_1_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_1_2"
        elif 0.02 <= profit_init_ratio < 0.03:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_2_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_2_2"
        elif 0.03 <= profit_init_ratio < 0.04:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_3_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_3_2"
        elif 0.04 <= profit_init_ratio < 0.05:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_4_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_4_2"
        elif 0.05 <= profit_init_ratio < 0.06:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_5_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_5_2"
        elif 0.06 <= profit_init_ratio < 0.07:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_6_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_6_2"
        elif 0.07 <= profit_init_ratio < 0.08:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_7_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_7_2"
        elif 0.08 <= profit_init_ratio < 0.09:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_8_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_8_2"
        elif 0.09 <= profit_init_ratio < 0.10:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_9_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_9_2"
        elif 0.10 <= profit_init_ratio < 0.11:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_10_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_10_2"
        elif 0.11 <= profit_init_ratio < 0.12:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_11_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_11_2"
        elif 0.12 <= profit_init_ratio:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] > 50.0)
            and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_12_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] > 0.0)
            and (last_candle["CMF_20_1h"] > 0.0)
            and (last_candle["CMF_20_4h"] > 0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_12_2"
      else:
        if 0.001 <= profit_init_ratio < 0.01:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_0_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_0_2"
        elif 0.01 <= profit_init_ratio < 0.02:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_1_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_1_2"
        elif 0.02 <= profit_init_ratio < 0.03:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_2_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_2_2"
        elif 0.03 <= profit_init_ratio < 0.04:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_3_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_3_2"
        elif 0.04 <= profit_init_ratio < 0.05:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_4_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_4_2"
        elif 0.05 <= profit_init_ratio < 0.06:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_5_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_5_2"
        elif 0.06 <= profit_init_ratio < 0.07:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_6_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_6_2"
        elif 0.07 <= profit_init_ratio < 0.08:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_7_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_7_2"
        elif 0.08 <= profit_init_ratio < 0.09:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_8_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_8_2"
        elif 0.09 <= profit_init_ratio < 0.10:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_9_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_9_2"
        elif 0.10 <= profit_init_ratio < 0.11:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_10_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_10_2"
        elif 0.11 <= profit_init_ratio < 0.12:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_11_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_11_2"
        elif 0.12 <= profit_init_ratio:
          if (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["RSI_14"] < 50.0)
            and (last_candle["RSI_14"] < previous_candle_1["RSI_14"])
            and (last_candle["CMF_20"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_12_1"
          elif (
            profit_init_ratio < (previous_profit - 0.03)
            and (last_candle["CMF_20"] < -0.0)
            and (last_candle["CMF_20_1h"] < -0.0)
            and (last_candle["CMF_20_4h"] < -0.0)
          ):
            return True, f"exit_profit_{mode_name}_t_12_2"
    else:
      return False, None

    return False, None

  # Calc Total Profit
  # ---------------------------------------------------------------------------------------------
  def calc_total_profit(
    self, trade: "Trade", filled_entries: "Orders", filled_exits: "Orders", exit_rate: float
  ) -> tuple:
    """
    Calculates the absolute profit for open trades.

    :param trade: trade object.
    :param filled_entries: Filled entries list.
    :param filled_exits: Filled exits list.
    :param exit_rate: The exit rate.
    :return tuple: The total profit in stake, ratio, ratio based on current stake, and ratio based on the first entry stake.
    """
    fee_open_rate = trade.fee_open if self.custom_fee_open_rate is None else self.custom_fee_open_rate
    fee_close_rate = trade.fee_close if self.custom_fee_close_rate is None else self.custom_fee_close_rate

    total_amount = 0.0
    total_stake = 0.0
    total_profit = 0.0
    current_stake = 0.0
    for entry_order in filled_entries:
      if trade.is_short:
        entry_stake = entry_order.safe_filled * entry_order.safe_price * (1 - fee_open_rate)
        total_amount += entry_order.safe_filled
        total_stake += entry_stake
        total_profit += entry_stake
      else:
        entry_stake = entry_order.safe_filled * entry_order.safe_price * (1 + fee_open_rate)
        total_amount += entry_order.safe_filled
        total_stake += entry_stake
        total_profit -= entry_stake
    for exit_order in filled_exits:
      if trade.is_short:
        exit_stake = exit_order.safe_filled * exit_order.safe_price * (1 + fee_close_rate)
        total_amount -= exit_order.safe_filled
        total_profit -= exit_stake
      else:
        exit_stake = exit_order.safe_filled * exit_order.safe_price * (1 - fee_close_rate)
        total_amount -= exit_order.safe_filled
        total_profit += exit_stake
    if trade.is_short:
      current_stake = total_amount * exit_rate * (1 + fee_close_rate)
      total_profit -= current_stake
    else:
      current_stake = total_amount * exit_rate * (1 - fee_close_rate)
      total_profit += current_stake
    if self.is_futures_mode:
      total_profit += trade.funding_fees
    total_profit_ratio = total_profit / total_stake
    current_profit_ratio = total_profit / current_stake
    init_profit_ratio = total_profit / filled_entries[0].cost
    return total_profit, total_profit_ratio, current_profit_ratio, init_profit_ratio

  # Custom Exit
  # ---------------------------------------------------------------------------------------------
  def custom_exit(
    self, pair: str, trade: "Trade", current_time: "datetime", current_rate: float, current_profit: float, **kwargs
  ):
    df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    last_candle = df.iloc[-1].squeeze()
    previous_candle_1 = df.iloc[-2].squeeze()
    previous_candle_2 = df.iloc[-3].squeeze()
    previous_candle_3 = df.iloc[-4].squeeze()
    previous_candle_4 = df.iloc[-5].squeeze()
    previous_candle_5 = df.iloc[-6].squeeze()

    enter_tag = "empty"
    if hasattr(trade, "enter_tag") and trade.enter_tag is not None:
      enter_tag = trade.enter_tag
    enter_tags = enter_tag.split()

    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)

    profit_stake = 0.0
    profit_ratio = 0.0
    profit_current_stake_ratio = 0.0
    profit_init_ratio = 0.0
    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, current_rate
    )

    max_profit = (trade.max_rate - trade.open_rate) / trade.open_rate
    max_loss = (trade.open_rate - trade.min_rate) / trade.min_rate

    count_of_entries = len(filled_entries)
    if count_of_entries > 1:
      initial_entry = filled_entries[0]
      if initial_entry is not None and initial_entry.average is not None:
        max_profit = (trade.max_rate - initial_entry.average) / initial_entry.average
        max_loss = (initial_entry.average - trade.min_rate) / trade.min_rate

    # Long Normal mode
    if any(c in self.long_normal_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_normal(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long Pump mode
    if any(c in self.long_pump_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_pump(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long Quick mode
    if any(c in self.long_quick_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_quick(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long Rebuy mode
    if all(c in self.long_rebuy_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_rebuy(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long high profit mode
    if any(c in self.long_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_high_profit(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # Long rapid mode
    if any(c in self.long_rapid_mode_tags for c in enter_tags):
      sell, signal_name = self.long_exit_rapid(
        pair,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
      if sell and (signal_name is not None):
        return f"{signal_name} ( {enter_tag})"

    # # Long grind mode
    # if all(c in self.long_grind_mode_tags for c in enter_tags):
    #   sell, signal_name = self.long_exit_grind(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Short normal mode
    # if any(c in self.short_normal_mode_tags for c in enter_tags):
    #   sell, signal_name = self.short_exit_normal(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Short Pump mode
    # if any(c in self.short_pump_mode_tags for c in enter_tags):
    #   sell, signal_name = self.short_exit_pump(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Short Quick mode
    # if any(c in self.short_quick_mode_tags for c in enter_tags):
    #   sell, signal_name = self.short_exit_quick(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Short Rebuy mode
    # if all(c in self.short_rebuy_mode_tags for c in enter_tags):
    #   sell, signal_name = self.short_exit_rebuy(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Short high profit mode
    # if any(c in self.short_mode_tags for c in enter_tags):
    #   sell, signal_name = self.short_exit_high_profit(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Short rapid mode
    # if any(c in self.short_rapid_mode_tags for c in enter_tags):
    #   sell, signal_name = self.short_exit_rapid(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Trades not opened by X4
    # if not trade.is_short and (
    #   not any(
    #     c
    #     in (
    #       self.long_normal_mode_tags
    #       + self.long_pump_mode_tags
    #       + self.long_quick_mode_tags
    #       + self.long_rebuy_mode_tags
    #       + self.long_mode_tags
    #       + self.long_rapid_mode_tags
    #       + self.long_grind_mode_tags
    #     )
    #     for c in enter_tags
    #   )
    # ):
    #   # use normal mode for such trades
    #   sell, signal_name = self.long_exit_normal(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    # # Trades not opened by X4
    # if trade.is_short and (
    #   not any(
    #     c
    #     in (
    #       self.short_normal_mode_tags
    #       + self.short_pump_mode_tags
    #       + self.short_quick_mode_tags
    #       + self.short_rebuy_mode_tags
    #       + self.short_mode_tags
    #       + self.short_rapid_mode_tags
    #       + self.short_grind_mode_tags
    #     )
    #     for c in enter_tags
    #   )
    # ):
    #   # use normal mode for such trades
    #   sell, signal_name = self.short_exit_normal(
    #     pair,
    #     current_rate,
    #     profit_stake,
    #     profit_ratio,
    #     profit_current_stake_ratio,
    #     profit_init_ratio,
    #     max_profit,
    #     max_loss,
    #     filled_entries,
    #     filled_exits,
    #     last_candle,
    #     previous_candle_1,
    #     previous_candle_2,
    #     previous_candle_3,
    #     previous_candle_4,
    #     previous_candle_5,
    #     trade,
    #     current_time,
    #     enter_tags,
    #   )
    #   if sell and (signal_name is not None):
    #     return f"{signal_name} ( {enter_tag})"

    return None

  # Custom Stake Amount
  # ---------------------------------------------------------------------------------------------
  def custom_stake_amount(
    self,
    pair: str,
    current_time: datetime,
    current_rate: float,
    proposed_stake: float,
    min_stake: Optional[float],
    max_stake: float,
    leverage: float,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> float:
    enter_tags = entry_tag.split()
    if side == "long":
      # Rebuy mode
      if all(c in self.long_rebuy_mode_tags for c in enter_tags) or (
        any(c in self.long_rebuy_mode_tags for c in enter_tags)
        and all(c in (self.long_rebuy_mode_tags + self.long_grind_mode_tags) for c in enter_tags)
      ):
        stake_multiplier = self.rebuy_mode_stake_multiplier
        # Low stakes, on Binance mostly
        if (proposed_stake * self.rebuy_mode_stake_multiplier) < min_stake:
          stake_multiplier = self.rebuy_mode_stake_multiplier_alt
        return proposed_stake * stake_multiplier
      # Grind mode
      elif all(c in self.long_grind_mode_tags for c in enter_tags):
        for _, item in enumerate(
          self.grind_mode_stake_multiplier_futures if self.is_futures_mode else self.grind_mode_stake_multiplier_spot
        ):
          if (proposed_stake * item) > min_stake:
            stake_multiplier = item
            return proposed_stake * stake_multiplier
      else:
        stake_multiplier = (
          self.regular_mode_stake_multiplier_futures[0]
          if self.is_futures_mode
          else self.regular_mode_stake_multiplier_spot[0]
        )
        if (proposed_stake * stake_multiplier) > min_stake:
          return proposed_stake * stake_multiplier
        else:
          return min_stake
    else:
      # Rebuy mode
      if all(c in self.short_rebuy_mode_tags for c in enter_tags) or (
        any(c in self.short_rebuy_mode_tags for c in enter_tags)
        and all(c in (self.short_rebuy_mode_tags + self.short_grind_mode_tags) for c in enter_tags)
      ):
        stake_multiplier = self.rebuy_mode_stake_multiplier
        # Low stakes, on Binance mostly
        if (proposed_stake * self.rebuy_mode_stake_multiplier) < min_stake:
          stake_multiplier = self.rebuy_mode_stake_multiplier_alt
        return proposed_stake * stake_multiplier
      # Grind mode
      elif all(c in self.short_grind_mode_tags for c in enter_tags):
        for _, item in enumerate(
          self.grind_mode_stake_multiplier_futures if self.is_futures_mode else self.grind_mode_stake_multiplier_spot
        ):
          if (proposed_stake * item) > min_stake:
            stake_multiplier = item
            return proposed_stake * stake_multiplier
      else:
        stake_multiplier = (
          self.regular_mode_stake_multiplier_futures[0]
          if self.is_futures_mode
          else self.regular_mode_stake_multiplier_spot[0]
        )
        if (proposed_stake * stake_multiplier) > min_stake:
          return proposed_stake * stake_multiplier
        else:
          return min_stake

    return proposed_stake

  # Adjust Trade Position
  # ---------------------------------------------------------------------------------------------
  def adjust_trade_position(
    self,
    trade: Trade,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ):
    if self.position_adjustment_enable == False:
      return None

    enter_tag = "empty"
    if hasattr(trade, "enter_tag") and trade.enter_tag is not None:
      enter_tag = trade.enter_tag
    enter_tags = enter_tag.split()

    # Rebuy mode
    if not trade.is_short and (
      all(c in self.long_rebuy_mode_tags for c in enter_tags)
      or (
        any(c in self.long_rebuy_mode_tags for c in enter_tags)
        and all(c in (self.long_rebuy_mode_tags + self.long_grind_mode_tags) for c in enter_tags)
      )
    ):
      return self.long_rebuy_adjust_trade_position(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    # Grinding
    elif not trade.is_short and (
      any(
        c
        in (
          self.long_normal_mode_tags
          + self.long_pump_mode_tags
          + self.long_quick_mode_tags
          + self.long_mode_tags
          + self.long_rapid_mode_tags
          + self.long_grind_mode_tags
        )
        for c in enter_tags
      )
      or not any(
        c
        in (
          self.long_normal_mode_tags
          + self.long_pump_mode_tags
          + self.long_quick_mode_tags
          + self.long_rebuy_mode_tags
          + self.long_mode_tags
          + self.long_rapid_mode_tags
          + self.long_grind_mode_tags
        )
        for c in enter_tags
      )
    ):
      return self.long_grind_adjust_trade_position(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    elif trade.is_short and (
      any(
        c
        in (
          self.short_normal_mode_tags
          + self.short_pump_mode_tags
          + self.short_quick_mode_tags
          + self.short_mode_tags
          + self.short_rapid_mode_tags
          + self.short_grind_mode_tags
        )
        for c in enter_tags
      )
      or not any(
        c
        in (
          self.short_normal_mode_tags
          + self.short_pump_mode_tags
          + self.short_quick_mode_tags
          + self.short_rebuy_mode_tags
          + self.short_mode_tags
          + self.short_rapid_mode_tags
          + self.short_grind_mode_tags
        )
        for c in enter_tags
      )
    ):
      return self.short_grind_adjust_trade_position(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    return None

  # Informative Pairs
  # ---------------------------------------------------------------------------------------------
  def informative_pairs(self):
    # get access to all pairs available in whitelist.
    pairs = self.dp.current_whitelist()
    # Assign tf to each pair so they can be downloaded and cached for strategy.
    informative_pairs = []
    for info_timeframe in self.info_timeframes:
      informative_pairs.extend([(pair, info_timeframe) for pair in pairs])

    if self.config["stake_currency"] in [
      "USDT",
      "BUSD",
      "USDC",
      "DAI",
      "TUSD",
      "FDUSD",
      "PAX",
      "USD",
      "EUR",
      "GBP",
      "TRY",
    ]:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = f"BTC/{self.config['stake_currency']}:{self.config['stake_currency']}"
      else:
        btc_info_pair = f"BTC/{self.config['stake_currency']}"
    else:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = "BTC/USDT:USDT"
      else:
        btc_info_pair = "BTC/USDT"

    informative_pairs.extend([(btc_info_pair, btc_info_timeframe) for btc_info_timeframe in self.btc_info_timeframes])

    return informative_pairs

  # Informative 1d Timeframe Indicators
  # ---------------------------------------------------------------------------------------------
  def informative_1d_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    # Get the informative pair
    informative_1d = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # informative_1d_indicators_pandas_ta = pta.Strategy(
    #   name="informative_1d_indicators_pandas_ta",
    #   ta=[
    #     # RSI
    #     {"kind": "rsi", "length": 3},
    #     {"kind": "rsi", "length": 14},
    #     # {"kind": "rsi", "length": 20},
    #     # EMA
    #     # {"kind": "ema", "length": 12},
    #     # {"kind": "ema", "length": 16},
    #     # {"kind": "ema", "length": 20},
    #     # {"kind": "ema", "length": 26},
    #     # {"kind": "ema", "length": 50},
    #     # {"kind": "ema", "length": 100},
    #     # {"kind": "ema", "length": 200},
    #     # SMA
    #     # {"kind": "sma", "length": 16},
    #     # MFI
    #     {"kind": "mfi"},
    #     # CMF
    #     {"kind": "cmf"},
    #     # Williams %R
    #     {"kind": "willr", "length": 14},
    #     # STOCHRSI
    #     {"kind": "stochrsi"},
    #     # KST
    #     {"kind": "kst"},
    #     # ROC
    #     {"kind": "roc"},
    #     # AROON
    #     {"kind": "aroon"},
    #   ],
    # )
    # informative_1d.ta.study(informative_1d_indicators_pandas_ta, cores=self.num_cores_indicators_calc)
    # RSI
    informative_1d["RSI_3"] = pta.rsi(informative_1d["close"], length=3)
    informative_1d["RSI_14"] = pta.rsi(informative_1d["close"], length=14)
    # BB 20 - STD2
    bbands_20_2 = pta.bbands(informative_1d["close"], length=20)
    informative_1d["BBL_20_2.0"] = bbands_20_2["BBL_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1d["BBM_20_2.0"] = bbands_20_2["BBM_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1d["BBU_20_2.0"] = bbands_20_2["BBU_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1d["BBB_20_2.0"] = bbands_20_2["BBB_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1d["BBP_20_2.0"] = bbands_20_2["BBP_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    # CTI
    informative_1d["CTI_20"] = pta.cti(informative_1d["close"], length=20)
    # Williams %R
    informative_1d["WILLR_14"] = pta.willr(
      informative_1d["high"], informative_1d["low"], informative_1d["close"], length=14
    )
    # Candle change
    informative_1d["change_pct"] = (informative_1d["close"] - informative_1d["open"]) / informative_1d["open"] * 100.0

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1d_indicators took: {tok - tik:0.4f} seconds.")

    return informative_1d

  # Informative 4h Timeframe Indicators
  # ---------------------------------------------------------------------------------------------
  def informative_4h_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    # Get the informative pair
    informative_4h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # informative_4h_indicators_pandas_ta = pta.Strategy(
    #   name="informative_4h_indicators_pandas_ta",
    #   ta=[
    #     # RSI
    #     {"kind": "rsi", "length": 3},
    #     {"kind": "rsi", "length": 14},
    #     # {"kind": "rsi", "length": 20},
    #     # EMA
    #     {"kind": "ema", "length": 12},
    #     # {"kind": "ema", "length": 16},
    #     # {"kind": "ema", "length": 20},
    #     {"kind": "ema", "length": 26},
    #     # {"kind": "ema", "length": 50},
    #     # {"kind": "ema", "length": 100},
    #     {"kind": "ema", "length": 200},
    #     # SMA
    #     # {"kind": "sma", "length": 16},
    #     # BB 20 - STD2
    #     {"kind": "bbands", "length": 20},
    #     # MFI
    #     {"kind": "mfi"},
    #     # CMF
    #     {"kind": "cmf"},
    #     # Williams %R
    #     {"kind": "willr", "length": 14},
    #     # CTI
    #     {"kind": "cti", "length": 20},
    #     # STOCHRSI
    #     {"kind": "stochrsi"},
    #     # KST
    #     {"kind": "kst"},
    #     # ROC
    #     {"kind": "roc"},
    #     # AROON
    #     {"kind": "aroon"},
    #     # UO
    #     {"kind": "uo"},
    #     # AO
    #     {"kind": "ao"},
    #   ],
    # )
    # informative_4h.ta.study(informative_4h_indicators_pandas_ta, cores=self.num_cores_indicators_calc)
    # RSI
    informative_4h["RSI_3"] = pta.rsi(informative_4h["close"], length=3)
    informative_4h["RSI_14"] = pta.rsi(informative_4h["close"], length=14)
    # EMA
    informative_4h["EMA_12"] = pta.ema(informative_4h["close"], length=12)
    informative_4h["EMA_200"] = pta.ema(informative_4h["close"], length=200, fillna=0.0)
    # BB 20 - STD2
    bbands_20_2 = pta.bbands(informative_4h["close"], length=20)
    informative_4h["BBL_20_2.0"] = bbands_20_2["BBL_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_4h["BBM_20_2.0"] = bbands_20_2["BBM_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_4h["BBU_20_2.0"] = bbands_20_2["BBU_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_4h["BBB_20_2.0"] = bbands_20_2["BBB_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_4h["BBP_20_2.0"] = bbands_20_2["BBP_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    # MFI
    informative_4h["MFI_14"] = pta.mfi(
      informative_4h["high"], informative_4h["low"], informative_4h["close"], informative_4h["volume"], length=14
    )
    # CMF
    informative_4h["CMF_20"] = pta.cmf(
      informative_4h["high"], informative_4h["low"], informative_4h["close"], informative_4h["volume"], length=20
    )
    # CTI
    informative_4h["CTI_20"] = pta.cti(informative_4h["close"], length=20)
    # Williams %R
    informative_4h["WILLR_14"] = pta.willr(
      informative_4h["high"], informative_4h["low"], informative_4h["close"], length=14
    )
    # AROON
    aroon_14 = pta.aroon(informative_4h["high"], informative_4h["low"], length=14)
    informative_4h["AROONU_14"] = aroon_14["AROONU_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    informative_4h["AROOND_14"] = aroon_14["AROOND_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    # KST
    kst = pta.kst(informative_4h["close"])
    informative_4h["KST_10_15_20_30_10_10_10_15"] = (
      kst["KST_10_15_20_30_10_10_10_15"] if isinstance(kst, pd.DataFrame) else np.nan
    )
    informative_4h["KSTs_9"] = kst["KSTs_9"] if isinstance(kst, pd.DataFrame) else np.nan
    # Candle change
    informative_4h["change_pct"] = (informative_4h["close"] - informative_4h["open"]) / informative_4h["open"] * 100.0

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1d_indicators took: {tok - tik:0.4f} seconds.")

    return informative_4h

  # Informative 1h Timeframe Indicators
  # ---------------------------------------------------------------------------------------------
  def informative_1h_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."
    # Get the informative pair
    informative_1h = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # informative_1h_indicators_pandas_ta = pta.Strategy(
    #   name="informative_1h_indicators_pandas_ta",
    #   ta=[
    #     # RSI
    #     {"kind": "rsi", "length": 3},
    #     {"kind": "rsi", "length": 14},
    #     # {"kind": "rsi", "length": 20},
    #     # EMA
    #     {"kind": "ema", "length": 12},
    #     # {"kind": "ema", "length": 16},
    #     {"kind": "ema", "length": 20},
    #     {"kind": "ema", "length": 26},
    #     # {"kind": "ema", "length": 50},
    #     # {"kind": "ema", "length": 100},
    #     {"kind": "ema", "length": 200},
    #     # SMA
    #     # {"kind": "sma", "length": 16},
    #     # BB 20 - STD2
    #     {"kind": "bbands", "length": 20},
    #     # MFI
    #     {"kind": "mfi"},
    #     # CMF
    #     {"kind": "cmf"},
    #     # Williams %R
    #     {"kind": "willr", "length": 14},
    #     # CTI
    #     {"kind": "cti", "length": 20},
    #     # STOCHRSI
    #     {"kind": "stochrsi"},
    #     # KST
    #     {"kind": "kst"},
    #     # ROC
    #     {"kind": "roc"},
    #     # AROON
    #     {"kind": "aroon"},
    #     # UO
    #     {"kind": "uo"},
    #     # AO
    #     {"kind": "ao"},
    #   ],
    # )
    # informative_1h.ta.study(informative_1h_indicators_pandas_ta, cores=self.num_cores_indicators_calc)
    # RSI
    informative_1h["RSI_3"] = pta.rsi(informative_1h["close"], length=3)
    informative_1h["RSI_14"] = pta.rsi(informative_1h["close"], length=14)
    # EMA
    informative_1h["EMA_12"] = pta.ema(informative_1h["close"], length=12)
    informative_1h["EMA_200"] = pta.ema(informative_1h["close"], length=200, fillna=0.0)
    # BB 20 - STD2
    bbands_20_2 = pta.bbands(informative_1h["close"], length=20)
    informative_1h["BBL_20_2.0"] = bbands_20_2["BBL_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1h["BBM_20_2.0"] = bbands_20_2["BBM_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1h["BBU_20_2.0"] = bbands_20_2["BBU_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1h["BBB_20_2.0"] = bbands_20_2["BBB_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    informative_1h["BBP_20_2.0"] = bbands_20_2["BBP_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    # MFI
    informative_1h["MFI_14"] = pta.mfi(
      informative_1h["high"], informative_1h["low"], informative_1h["close"], informative_1h["volume"], length=14
    )
    # CMF
    informative_1h["CMF_20"] = pta.cmf(
      informative_1h["high"], informative_1h["low"], informative_1h["close"], informative_1h["volume"], length=20
    )
    # CTI
    informative_1h["CTI_20"] = pta.cti(informative_1h["close"], length=20)
    informative_1h["CTI_40"] = pta.cti(informative_1h["close"], length=40)
    # Williams %R
    informative_1h["WILLR_14"] = pta.willr(
      informative_1h["high"], informative_1h["low"], informative_1h["close"], length=14
    )
    informative_1h["WILLR_84"] = pta.willr(
      informative_1h["high"], informative_1h["low"], informative_1h["close"], length=84
    )
    # AROON
    aroon_14 = pta.aroon(informative_1h["high"], informative_1h["low"], length=14)
    informative_1h["AROONU_14"] = aroon_14["AROONU_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    informative_1h["AROOND_14"] = aroon_14["AROOND_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    # KST
    kst = pta.kst(informative_1h["close"])
    informative_1h["KST_10_15_20_30_10_10_10_15"] = (
      kst["KST_10_15_20_30_10_10_10_15"] if isinstance(kst, pd.DataFrame) else np.nan
    )
    informative_1h["KSTs_9"] = kst["KSTs_9"] if isinstance(kst, pd.DataFrame) else np.nan
    # OBV
    informative_1h["OBV"] = pta.obv(informative_1h["close"], informative_1h["volume"])
    informative_1h["OBV_change_pct"] = (
      (informative_1h["OBV"] - informative_1h["OBV"].shift(1)) / abs(informative_1h["OBV"].shift(1))
    ) * 100.0
    # Candle change
    informative_1h["change_pct"] = (informative_1h["close"] - informative_1h["open"]) / informative_1h["open"] * 100.0

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_1h_indicators took: {tok - tik:0.4f} seconds.")

    return informative_1h

  # Informative 15m Timeframe Indicators
  # ---------------------------------------------------------------------------------------------
  def informative_15m_indicators(self, metadata: dict, info_timeframe) -> DataFrame:
    tik = time.perf_counter()
    assert self.dp, "DataProvider is required for multiple timeframes."

    # Get the informative pair
    informative_15m = self.dp.get_pair_dataframe(pair=metadata["pair"], timeframe=info_timeframe)

    # Indicators
    # -----------------------------------------------------------------------------------------
    # informative_15m_indicators_pandas_ta = pta.Strategy(
    #   name="informative_15m_indicators_pandas_ta",
    #   ta=[
    #     # RSI
    #     {"kind": "rsi", "length": 3},
    #     {"kind": "rsi", "length": 14},
    #     # {"kind": "rsi", "length": 20},
    #     # EMA
    #     {"kind": "ema", "length": 12},
    #     # {"kind": "ema", "length": 16},
    #     # {"kind": "ema", "length": 20},
    #     # {"kind": "ema", "length": 26},
    #     # {"kind": "ema", "length": 50},
    #     # {"kind": "ema", "length": 100},
    #     # {"kind": "ema", "length": 200},
    #     # SMA
    #     # {"kind": "sma", "length": 16},
    #     # BB 20 - STD2
    #     {"kind": "bbands", "length": 20},
    #     # Williams %R
    #     {"kind": "willr", "length": 14},
    #     # CTI
    #     {"kind": "cti", "length": 20},
    #     # STOCHRSI
    #     {"kind": "stochrsi"},
    #     # ROC
    #     {"kind": "roc"},
    #     # AROON
    #     {"kind": "aroon"},
    #     # UO
    #     {"kind": "uo"},
    #     # AO
    #     {"kind": "ao"},
    #   ],
    # )
    # informative_15m.ta.study(informative_15m_indicators_pandas_ta, cores=self.num_cores_indicators_calc)
    # RSI
    informative_15m["RSI_3"] = pta.rsi(informative_15m["close"], length=3)
    informative_15m["RSI_14"] = pta.rsi(informative_15m["close"], length=14)
    # MFI
    informative_15m["MFI_14"] = pta.mfi(
      informative_15m["high"], informative_15m["low"], informative_15m["close"], informative_15m["volume"], length=14
    )
    # CMF
    informative_15m["CMF_20"] = pta.cmf(
      informative_15m["high"], informative_15m["low"], informative_15m["close"], informative_15m["volume"], length=20
    )
    # AROON
    aroon_14 = pta.aroon(informative_15m["high"], informative_15m["low"], length=14)
    informative_15m["AROONU_14"] = aroon_14["AROONU_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    informative_15m["AROOND_14"] = aroon_14["AROOND_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    # OBV
    informative_15m["OBV"] = pta.obv(informative_15m["close"], informative_15m["volume"])
    informative_15m["OBV_change_pct"] = (
      (informative_15m["OBV"] - informative_15m["OBV"].shift(1)) / abs(informative_15m["OBV"].shift(1))
    ) * 100.0
    # Candle change
    informative_15m["change_pct"] = (
      (informative_15m["close"] - informative_15m["open"]) / informative_15m["open"] * 100.0
    )

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] informative_15m_indicators took: {tok - tik:0.4f} seconds.")

    return informative_15m

  # Coin Pair Base Timeframe Indicators
  # ---------------------------------------------------------------------------------------------
  def base_tf_5m_indicators(self, metadata: dict, df: DataFrame) -> DataFrame:
    tik = time.perf_counter()

    # Indicators
    # base_tf_5m_indicators_pandas_ta = pta.Strategy(
    #   name="base_tf_5m_indicators_pandas_ta",
    #   ta=[
    #     # RSI
    #     {"kind": "rsi", "length": 3},
    #     {"kind": "rsi", "length": 4},
    #     {"kind": "rsi", "length": 14},
    #     {"kind": "rsi", "length": 20},
    #     # EMA
    #     {"kind": "ema", "length": 3},
    #     {"kind": "ema", "length": 9},
    #     {"kind": "ema", "length": 12},
    #     {"kind": "ema", "length": 16},
    #     {"kind": "ema", "length": 20},
    #     {"kind": "ema", "length": 26},
    #     {"kind": "ema", "length": 50},
    #     {"kind": "ema", "length": 100},
    #     {"kind": "ema", "length": 200},
    #     # SMA
    #     {"kind": "sma", "length": 16},
    #     {"kind": "sma", "length": 30},
    #     {"kind": "sma", "length": 75},
    #     {"kind": "sma", "length": 200},
    #     # BB 20 - STD2
    #     {"kind": "bbands", "length": 20},
    #     # BB 40 - STD2
    #     {"kind": "bbands", "length": 40},
    #     # Williams %R
    #     {"kind": "willr", "length": 14},
    #     {"kind": "willr", "length": 480},
    #     # CTI
    #     {"kind": "cti", "length": 20},
    #     # MFI
    #     {"kind": "mfi"},
    #     # CMF
    #     {"kind": "cmf"},
    #     # CCI
    #     {"kind": "cci", "length": 20},
    #     # Hull Moving Average
    #     {"kind": "hma", "length": 55},
    #     {"kind": "hma", "length": 70},
    #     # ZL MA
    #     # {"kind": "zlma", "length": 50, "mamode":"linreg"},
    #     # Heiken Ashi
    #     # {"kind": "ha"},
    #     # STOCHRSI
    #     {"kind": "stochrsi"},
    #     # KST
    #     {"kind": "kst"},
    #     # ROC
    #     {"kind": "roc"},
    #     # AROON
    #     {"kind": "aroon"},
    #     # UO
    #     {"kind": "uo"},
    #     # AO
    #     {"kind": "ao"},
    #     # OBV
    #     {"kind": "obv"},
    #   ],
    # )
    # df.ta.study(base_tf_5m_indicators_pandas_ta, cores=self.num_cores_indicators_calc)
    # RSI
    df["RSI_3"] = pta.rsi(df["close"], length=3)
    df["RSI_4"] = pta.rsi(df["close"], length=4)
    df["RSI_14"] = pta.rsi(df["close"], length=14)
    df["RSI_20"] = pta.rsi(df["close"], length=20)
    # EMA
    df["EMA_3"] = pta.ema(df["close"], length=3)
    df["EMA_9"] = pta.ema(df["close"], length=9)
    df["EMA_12"] = pta.ema(df["close"], length=12)
    df["EMA_16"] = pta.ema(df["close"], length=16)
    df["EMA_20"] = pta.ema(df["close"], length=20)
    df["EMA_26"] = pta.ema(df["close"], length=26)
    df["EMA_50"] = pta.ema(df["close"], length=50)
    df["EMA_200"] = pta.ema(df["close"], length=200, fillna=0.0)
    # SMA
    df["SMA_16"] = pta.sma(df["close"], length=16)
    df["SMA_30"] = pta.sma(df["close"], length=30)
    # BB 20 - STD2
    bbands_20_2 = pta.bbands(df["close"], length=20)
    df["BBL_20_2.0"] = bbands_20_2["BBL_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    df["BBM_20_2.0"] = bbands_20_2["BBM_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    df["BBU_20_2.0"] = bbands_20_2["BBU_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    df["BBB_20_2.0"] = bbands_20_2["BBB_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    df["BBP_20_2.0"] = bbands_20_2["BBP_20_2.0"] if isinstance(bbands_20_2, pd.DataFrame) else np.nan
    # MFI
    df["MFI_14"] = pta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14)
    # CMF
    df["CMF_20"] = pta.cmf(df["high"], df["low"], df["close"], df["volume"], length=20)
    # Williams %R
    df["WILLR_14"] = pta.willr(df["high"], df["low"], df["close"], length=14)
    df["WILLR_480"] = pta.willr(df["high"], df["low"], df["close"], length=480)
    # CTI
    df["CTI_20"] = pta.cti(df["close"], length=20)
    # AROON
    aroon_14 = pta.aroon(df["high"], df["low"], length=14)
    df["AROONU_14"] = aroon_14["AROONU_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    df["AROOND_14"] = aroon_14["AROOND_14"] if isinstance(aroon_14, pd.DataFrame) else np.nan
    # KST
    kst = pta.kst(df["close"])
    df["KST_10_15_20_30_10_10_10_15"] = kst["KST_10_15_20_30_10_10_10_15"] if isinstance(kst, pd.DataFrame) else np.nan
    df["KSTs_9"] = kst["KSTs_9"] if isinstance(kst, pd.DataFrame) else np.nan
    # OBV
    df["OBV"] = pta.obv(df["close"], df["volume"])
    df["OBV_change_pct"] = ((df["OBV"] - df["OBV"].shift(1)) / abs(df["OBV"].shift(1))) * 100.0
    # Candle change
    df["change_pct"] = (df["close"] - df["open"]) / df["open"] * 100.0
    # Close max
    df["close_max_48"] = df["close"].rolling(48).max()

    # -----------------------------------------------------------------------------------------

    # Global protections
    # -----------------------------------------------------------------------------------------
    if not self.config["runmode"].value in ("live", "dry_run"):
      # Backtest age filter
      df["bt_agefilter_ok"] = False
      df.loc[df.index > (12 * 24 * self.bt_min_age_days), "bt_agefilter_ok"] = True
    else:
      # Exchange downtime protection
      df["live_data_ok"] = df["volume"].rolling(window=72, min_periods=72).min() > 0

    # Performance logging
    # -----------------------------------------------------------------------------------------
    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] base_tf_5m_indicators took: {tok - tik:0.4f} seconds.")

    return df

  # Coin Pair Indicator Switch Case
  # ---------------------------------------------------------------------------------------------
  def info_switcher(self, metadata: dict, info_timeframe) -> DataFrame:
    if info_timeframe == "1d":
      return self.informative_1d_indicators(metadata, info_timeframe)
    elif info_timeframe == "4h":
      return self.informative_4h_indicators(metadata, info_timeframe)
    elif info_timeframe == "1h":
      return self.informative_1h_indicators(metadata, info_timeframe)
    elif info_timeframe == "15m":
      return self.informative_15m_indicators(metadata, info_timeframe)
    else:
      raise RuntimeError(f"{info_timeframe} not supported as informative timeframe for BTC pair.")

  # BTC 1D Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_1d_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_1d = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------
    # btc_info_1d_indicators_pandas_ta = pta.Strategy(
    #   name="btc_info_1d_indicators_pandas_ta",
    #   ta=[
    #     # RSI
    #     # {"kind": "rsi", "length": 3},
    #     {"kind": "rsi", "length": 14},
    #     # {"kind": "rsi", "length": 20},
    #     # EMA
    #     # {"kind": "ema", "length": 12},
    #     # {"kind": "ema", "length": 16},
    #     # {"kind": "ema", "length": 20},
    #     # {"kind": "ema", "length": 26},
    #     # {"kind": "ema", "length": 50},
    #     # {"kind": "ema", "length": 100},
    #     # {"kind": "ema", "length": 200},
    #     # SMA
    #     # {"kind": "sma", "length": 16},
    #   ],
    # )
    # btc_info_1d.ta.study(btc_info_1d_indicators_pandas_ta, cores=self.num_cores_indicators_calc)

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_1d.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_1d_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_1d

  # BTC 4h Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_4h_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_4h = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_4h.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_4h_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_4h

  # BTC 1h Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_1h_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_1h = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_1h.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_1h_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_1h

  # BTC 15m Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_15m_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_15m = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_15m.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_15m_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_15m

  # BTC 5m Indicators
  # ---------------------------------------------------------------------------------------------
  def btc_info_5m_indicators(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    btc_info_5m = self.dp.get_pair_dataframe(btc_info_pair, btc_info_timeframe)
    # Indicators
    # -----------------------------------------------------------------------------------------

    # Add prefix
    # -----------------------------------------------------------------------------------------
    ignore_columns = ["date"]
    btc_info_5m.rename(columns=lambda s: f"btc_{s}" if s not in ignore_columns else s, inplace=True)

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] btc_info_5m_indicators took: {tok - tik:0.4f} seconds.")

    return btc_info_5m

  # BTC Indicator Switch Case
  # ---------------------------------------------------------------------------------------------
  def btc_info_switcher(self, btc_info_pair, btc_info_timeframe, metadata: dict) -> DataFrame:
    if btc_info_timeframe == "1d":
      return self.btc_info_1d_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "4h":
      return self.btc_info_4h_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "1h":
      return self.btc_info_1h_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "15m":
      return self.btc_info_15m_indicators(btc_info_pair, btc_info_timeframe, metadata)
    elif btc_info_timeframe == "5m":
      return self.btc_info_5m_indicators(btc_info_pair, btc_info_timeframe, metadata)
    else:
      raise RuntimeError(f"{btc_info_timeframe} not supported as informative timeframe for BTC pair.")

  # Populate Indicators
  # ---------------------------------------------------------------------------------------------
  def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
    tik = time.perf_counter()
    """
        --> BTC informative indicators
        ___________________________________________________________________________________________
        """
    if self.config["stake_currency"] in [
      "USDT",
      "BUSD",
      "USDC",
      "DAI",
      "TUSD",
      "FDUSD",
      "PAX",
      "USD",
      "EUR",
      "GBP",
      "TRY",
    ]:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = f"BTC/{self.config['stake_currency']}:{self.config['stake_currency']}"
      else:
        btc_info_pair = f"BTC/{self.config['stake_currency']}"
    else:
      if ("trading_mode" in self.config) and (self.config["trading_mode"] in ["futures", "margin"]):
        btc_info_pair = "BTC/USDT:USDT"
      else:
        btc_info_pair = "BTC/USDT"

    for btc_info_timeframe in self.btc_info_timeframes:
      btc_informative = self.btc_info_switcher(btc_info_pair, btc_info_timeframe, metadata)
      df = merge_informative_pair(df, btc_informative, self.timeframe, btc_info_timeframe, ffill=True)
      # Customize what we drop - in case we need to maintain some BTC informative ohlcv data
      # Default drop all
      drop_columns = {
        "1d": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "4h": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "1h": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "15m": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "5m": [f"btc_{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
      }.get(
        btc_info_timeframe,
        [f"{s}_{btc_info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
      )
      drop_columns.append(f"date_{btc_info_timeframe}")
      df.drop(columns=df.columns.intersection(drop_columns), inplace=True)

    """
        --> Indicators on informative timeframes
        ___________________________________________________________________________________________
        """
    for info_timeframe in self.info_timeframes:
      info_indicators = self.info_switcher(metadata, info_timeframe)
      df = merge_informative_pair(df, info_indicators, self.timeframe, info_timeframe, ffill=True)
      # Customize what we drop - in case we need to maintain some informative timeframe ohlcv data
      # Default drop all except base timeframe ohlcv data
      drop_columns = {
        "1d": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "4h": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "1h": [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]],
        "15m": [f"{s}_{info_timeframe}" for s in ["date", "high", "low", "volume"]],
      }.get(info_timeframe, [f"{s}_{info_timeframe}" for s in ["date", "open", "high", "low", "close", "volume"]])
      df.drop(columns=df.columns.intersection(drop_columns), inplace=True)

    """
        --> The indicators for the base timeframe  (5m)
        ___________________________________________________________________________________________
        """
    df = self.base_tf_5m_indicators(metadata, df)

    # df["zlma_50_1h"] = df["zlma_50_1h"].astype(np.float64).replace(to_replace=[np.nan, None], value=(0.0))
    # df["CTI_20_1d"] = df["CTI_20_1d"].astype(np.float64).replace(to_replace=[np.nan, None], value=(0.0))
    # df["WILLR_480_1h"] = df["WILLR_480_1h"].astype(np.float64).replace(to_replace=[np.nan, None], value=(-50.0))
    # df["WILLR_480_4h"] = df["WILLR_480_4h"].astype(np.float64).replace(to_replace=[np.nan, None], value=(-50.0))
    # df["RSI_14_1d"] = df["RSI_14_1d"].astype(np.float64).replace(to_replace=[np.nan, None], value=(50.0))

    # Global protections Long
    df["protections_long_global"] = True

    df["global_protections_long_pump"] = True

    df["global_protections_long_dump"] = True

    df["protections_long_rebuy"] = True

    # Global protections Short
    df["protections_short_global"] = True

    df["global_protections_short_pump"] = True

    df["global_protections_short_dump"] = True

    df["protections_short_rebuy"] = True

    tok = time.perf_counter()
    log.debug(f"[{metadata['pair']}] Populate indicators took a total of: {tok - tik:0.4f} seconds.")

    return df

  # Confirm Trade Entry
  # ---------------------------------------------------------------------------------------------
  def confirm_trade_entry(
    self,
    pair: str,
    order_type: str,
    amount: float,
    rate: float,
    time_in_force: str,
    current_time: datetime,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> bool:
    # allow force entries
    if entry_tag == "force_entry":
      return True

    # Grind mode
    entry_tags = entry_tag.split()
    if all(c in self.long_grind_mode_tags for c in entry_tags):
      is_pair_grind_mode = pair.split("/")[0] in self.grind_mode_coins
      if is_pair_grind_mode:
        num_open_grind_mode = 0
        open_trades = Trade.get_trades_proxy(is_open=True)
        for open_trade in open_trades:
          enter_tag = open_trade.enter_tag
          enter_tags = enter_tag.split()
          if all(c in self.long_grind_mode_tags for c in enter_tags):
            num_open_grind_mode += 1
        if num_open_grind_mode >= self.grind_mode_max_slots:
          # Reached the limit of grind mode open trades
          log.warning(f"Cancelling entry for {pair} due to reached the limit of grind mode open trades.")
          return False
      else:
        # The pair is not in the list of grind mode allowed
        log.warning(f"Cancelling entry for {pair} due to {pair} not in list of grind mode coins.")
        return False

    df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
    if len(df) >= 1:
      last_candle = df.iloc[-1].squeeze()
      if ("side" == "long" and rate > last_candle["close"]) or ("side" == "short" and rate < last_candle["close"]):
        slippage = (rate / last_candle["close"]) - 1.0
        if ("side" == "long" and slippage < self.max_slippage) or (
          "side" == "short" and slippage > -self.max_slippage
        ):
          return True
        else:
          log.warning(f"Cancelling entry for {pair} due to slippage {(slippage * 100.0):.2f}%")
          return False

    return True

  # Confirm Trade Exit
  # ---------------------------------------------------------------------------------------------
  def confirm_trade_exit(
    self,
    pair: str,
    trade: Trade,
    order_type: str,
    amount: float,
    rate: float,
    time_in_force: str,
    exit_reason: str,
    current_time: datetime,
    **kwargs,
  ) -> bool:
    # Allow force exits
    if exit_reason != "force_exit":
      if self._should_hold_trade(trade, rate, exit_reason):
        return False
      if exit_reason == "stop_loss":
        return False
      if self.exit_profit_only:
        if self.exit_profit_only:
          profit = 0.0
          if trade.realized_profit != 0.0:
            profit = ((rate - trade.open_rate) / trade.open_rate) * trade.stake_amount * (1 - trade.fee_close)
            profit = profit + trade.realized_profit
            profit = profit / trade.stake_amount
          else:
            profit = trade.calc_profit_ratio(rate)
          if profit < self.exit_profit_offset:
            return False

    self._remove_profit_target(pair)
    return True

  # Bot Loop Start
  # ---------------------------------------------------------------------------------------------
  def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
    if self.config["runmode"].value not in ("live", "dry_run"):
      return super().bot_loop_start(datetime, **kwargs)

    if self.hold_support_enabled:
      self.load_hold_trades_config()

    return super().bot_loop_start(current_time, **kwargs)

  # Leverage
  # ---------------------------------------------------------------------------------------------
  def leverage(
    self,
    pair: str,
    current_time: datetime,
    current_rate: float,
    proposed_leverage: float,
    max_leverage: float,
    entry_tag: Optional[str],
    side: str,
    **kwargs,
  ) -> float:
    enter_tags = entry_tag.split()
    if all(c in self.long_rebuy_mode_tags for c in enter_tags):
      return self.futures_mode_leverage_rebuy_mode
    elif all(c in self.long_grind_mode_tags for c in enter_tags):
      return self.futures_mode_leverage_grind_mode
    return self.futures_mode_leverage

  # Set Profit Target
  # ---------------------------------------------------------------------------------------------
  def _set_profit_target(
    self, pair: str, sell_reason: str, rate: float, current_profit: float, current_time: datetime
  ):
    self.target_profit_cache.data[pair] = {
      "rate": rate,
      "profit": current_profit,
      "sell_reason": sell_reason,
      "time_profit_reached": current_time.isoformat(),
    }
    self.target_profit_cache.save()

  # Remove Profit Target
  # ---------------------------------------------------------------------------------------------
  def _remove_profit_target(self, pair: str):
    if self.target_profit_cache is not None:
      self.target_profit_cache.data.pop(pair, None)
      self.target_profit_cache.save()

  # Get Hold Trades Config File
  # ---------------------------------------------------------------------------------------------
  def get_hold_trades_config_file(self):
    proper_holds_file_path = self.config["user_data_dir"].resolve() / "nfi-hold-trades.json"
    if proper_holds_file_path.is_file():
      return proper_holds_file_path

    strat_file_path = pathlib.Path(__file__)
    hold_trades_config_file_resolve = strat_file_path.resolve().parent / "hold-trades.json"
    if hold_trades_config_file_resolve.is_file():
      log.warning(
        "Please move %s to %s which is now the expected path for the holds file",
        hold_trades_config_file_resolve,
        proper_holds_file_path,
      )
      return hold_trades_config_file_resolve

    # The resolved path does not exist, is it a symlink?
    hold_trades_config_file_absolute = strat_file_path.absolute().parent / "hold-trades.json"
    if hold_trades_config_file_absolute.is_file():
      log.warning(
        "Please move %s to %s which is now the expected path for the holds file",
        hold_trades_config_file_absolute,
        proper_holds_file_path,
      )
      return hold_trades_config_file_absolute

  # Load Hold Trades Config
  # ---------------------------------------------------------------------------------------------
  def load_hold_trades_config(self):
    if self.hold_trades_cache is None:
      hold_trades_config_file = self.get_hold_trades_config_file()
      if hold_trades_config_file:
        log.warning("Loading hold support data from %s", hold_trades_config_file)
        self.hold_trades_cache = HoldsCache(hold_trades_config_file)

    if self.hold_trades_cache:
      self.hold_trades_cache.load()

  # Should Hold Trade
  # ---------------------------------------------------------------------------------------------
  def _should_hold_trade(self, trade: "Trade", rate: float, sell_reason: str) -> bool:
    if self.config["runmode"].value not in ("live", "dry_run"):
      return False

    if not self.hold_support_enabled:
      return False

    # Just to be sure our hold data is loaded, should be a no-op call after the first bot loop
    self.load_hold_trades_config()

    if not self.hold_trades_cache:
      # Cache hasn't been setup, likely because the corresponding file does not exist, sell
      return False

    if not self.hold_trades_cache.data:
      # We have no pairs we want to hold until profit, sell
      return False

    # By default, no hold should be done
    hold_trade = False

    trade_ids: dict = self.hold_trades_cache.data.get("trade_ids")
    if trade_ids and trade.id in trade_ids:
      trade_profit_ratio = trade_ids[trade.id]
      profit = 0.0
      if trade.realized_profit != 0.0:
        profit = ((rate - trade.open_rate) / trade.open_rate) * trade.stake_amount * (1 - trade.fee_close)
        profit = profit + trade.realized_profit
        profit = profit / trade.stake_amount
      else:
        profit = trade.calc_profit_ratio(rate)
      current_profit_ratio = profit
      if sell_reason == "force_sell":
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Force selling %s even though the current profit of %s < %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False
      elif current_profit_ratio >= trade_profit_ratio:
        # This pair is on the list to hold, and we reached minimum profit, sell
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Selling %s because the current profit of %s >= %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False

      # This pair is on the list to hold, and we haven't reached minimum profit, hold
      hold_trade = True

    trade_pairs: dict = self.hold_trades_cache.data.get("trade_pairs")
    if trade_pairs and trade.pair in trade_pairs:
      trade_profit_ratio = trade_pairs[trade.pair]
      profit = 0.0
      if trade.realized_profit != 0.0:
        profit = ((rate - trade.open_rate) / trade.open_rate) * trade.stake_amount * (1 - trade.fee_close)
        profit = profit + trade.realized_profit
        profit = profit / trade.stake_amount
      else:
        profit = trade.calc_profit_ratio(rate)
      current_profit_ratio = profit
      if sell_reason == "force_sell":
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Force selling %s even though the current profit of %s < %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False
      elif current_profit_ratio >= trade_profit_ratio:
        # This pair is on the list to hold, and we reached minimum profit, sell
        formatted_profit_ratio = f"{trade_profit_ratio * 100}%"
        formatted_current_profit_ratio = f"{current_profit_ratio * 100}%"
        log.warning(
          "Selling %s because the current profit of %s >= %s",
          trade,
          formatted_current_profit_ratio,
          formatted_profit_ratio,
        )
        return False

      # This pair is on the list to hold, and we haven't reached minimum profit, hold
      hold_trade = True

    return hold_trade

  # Populate Exit Trend
  # ---------------------------------------------------------------------------------------------
  def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    df.loc[:, "exit_long"] = 0
    df.loc[:, "exit_short"] = 0

    return df

  #
  # $$$$$$$$\ $$\   $$\ $$$$$$$$\ $$$$$$$\ $$\     $$\
  # $$  _____|$$$\  $$ |\__$$  __|$$  __$$\\$$\   $$  |
  # $$ |      $$$$\ $$ |   $$ |   $$ |  $$ |\$$\ $$  /
  # $$$$$\    $$ $$\$$ |   $$ |   $$$$$$$  | \$$$$  /
  # $$  __|   $$ \$$$$ |   $$ |   $$  __$$<   \$$  /
  # $$ |      $$ |\$$$ |   $$ |   $$ |  $$ |   $$ |
  # $$$$$$$$\ $$ | \$$ |   $$ |   $$ |  $$ |   $$ |
  # \________|\__|  \__|   \__|   \__|  \__|   \__|
  #

  #
  #  $$$$$$\   $$$$$$\  $$\   $$\ $$$$$$$\  $$$$$$\ $$$$$$$$\ $$$$$$\  $$$$$$\  $$\   $$\  $$$$$$\
  # $$  __$$\ $$  __$$\ $$$\  $$ |$$  __$$\ \_$$  _|\__$$  __|\_$$  _|$$  __$$\ $$$\  $$ |$$  __$$\
  # $$ /  \__|$$ /  $$ |$$$$\ $$ |$$ |  $$ |  $$ |     $$ |     $$ |  $$ /  $$ |$$$$\ $$ |$$ /  \__|
  # $$ |      $$ |  $$ |$$ $$\$$ |$$ |  $$ |  $$ |     $$ |     $$ |  $$ |  $$ |$$ $$\$$ |\$$$$$$\
  # $$ |      $$ |  $$ |$$ \$$$$ |$$ |  $$ |  $$ |     $$ |     $$ |  $$ |  $$ |$$ \$$$$ | \____$$\
  # $$ |  $$\ $$ |  $$ |$$ |\$$$ |$$ |  $$ |  $$ |     $$ |     $$ |  $$ |  $$ |$$ |\$$$ |$$\   $$ |
  # \$$$$$$  | $$$$$$  |$$ | \$$ |$$$$$$$  |$$$$$$\    $$ |   $$$$$$\  $$$$$$  |$$ | \$$ |\$$$$$$  |
  #  \______/  \______/ \__|  \__|\_______/ \______|   \__|   \______| \______/ \__|  \__| \______/
  #

  # Populate Entry Trend
  # ---------------------------------------------------------------------------------------------
  def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
    long_entry_conditions = []
    short_entry_conditions = []

    df.loc[:, "enter_tag"] = ""

    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt", "plot"]
    # the number of free slots
    current_free_slots = self.config["max_open_trades"]
    if not is_backtest:
      current_free_slots = self.config["max_open_trades"] - Trade.get_open_trade_count()
    # Grind mode
    num_open_long_grind_mode = 0
    is_pair_long_grind_mode = metadata["pair"].split("/")[0] in self.grind_mode_coins
    if not is_backtest:
      open_trades = Trade.get_trades_proxy(is_open=True)
      for open_trade in open_trades:
        enter_tag = open_trade.enter_tag
        if enter_tag is not None:
          enter_tags = enter_tag.split()
          if all(c in self.long_grind_mode_tags for c in enter_tags):
            num_open_long_grind_mode += 1
    # if BTC/ETH stake
    is_btc_stake = self.config["stake_currency"] in self.btc_stakes
    allowed_empty_candles = 144 if is_btc_stake else 60

    #
    #  /$$       /$$$$$$ /$$   /$$ /$$$$$$        /$$$$$$$$/$$   /$$/$$$$$$$$/$$$$$$$$/$$$$$$$
    # | $$      /$$__  $| $$$ | $$/$$__  $$      | $$_____| $$$ | $|__  $$__| $$_____| $$__  $$
    # | $$     | $$  \ $| $$$$| $| $$  \__/      | $$     | $$$$| $$  | $$  | $$     | $$  \ $$
    # | $$     | $$  | $| $$ $$ $| $$ /$$$$      | $$$$$  | $$ $$ $$  | $$  | $$$$$  | $$$$$$$/
    # | $$     | $$  | $| $$  $$$| $$|_  $$      | $$__/  | $$  $$$$  | $$  | $$__/  | $$__  $$
    # | $$     | $$  | $| $$\  $$| $$  \ $$      | $$     | $$\  $$$  | $$  | $$     | $$  \ $$
    # | $$$$$$$|  $$$$$$| $$ \  $|  $$$$$$/      | $$$$$$$| $$ \  $$  | $$  | $$$$$$$| $$  | $$
    # |________/\______/|__/  \__/\______/       |________|__/  \__/  |__/  |________|__/  |__/
    #

    for enabled_long_entry_signal in self.long_entry_signal_params:
      index = int(enabled_long_entry_signal.split("_")[3])
      item_buy_protection_list = [True]
      if self.long_entry_signal_params[f"{enabled_long_entry_signal}"]:
        # Long Entry Conditions Starts Here
        # -----------------------------------------------------------------------------------------
        long_entry_logic = []
        long_entry_logic.append(reduce(lambda x, y: x & y, item_buy_protection_list))

        # Condition #1 - Normal mode (Long).
        if index == 1:
          # Protections
          long_entry_logic.append(df["protections_long_global"] == True)
          long_entry_logic.append(df["global_protections_long_pump"] == True)
          long_entry_logic.append(df["global_protections_long_dump"] == True)

          long_entry_logic.append(df["RSI_3"] > 2.0)
          long_entry_logic.append(df["RSI_3"] < 40.0)
          long_entry_logic.append(df["RSI_3_15m"] < 70.0)
          long_entry_logic.append(df["RSI_3_1h"] > 2.0)
          long_entry_logic.append(df["RSI_3_1h"] < 70.0)
          long_entry_logic.append(df["RSI_3_4h"] > 2.0)
          long_entry_logic.append(df["RSI_3_4h"] < 70.0)

          # Logic
          long_entry_logic.append(df["EMA_26"] > df["EMA_12"])
          long_entry_logic.append((df["EMA_26"] - df["EMA_12"]) > (df["open"] * 0.030))
          long_entry_logic.append((df["EMA_26"].shift() - df["EMA_12"].shift()) > (df["open"] / 100.0))
          long_entry_logic.append(df["close"] < (df["BBL_20_2.0"] * 0.999))
          long_entry_logic.append(df["RSI_14"] > 20.0)

        # Condition #2 - Normal mode (Long).
        if index == 2:
          # Protections
          long_entry_logic.append(df["protections_long_global"] == True)
          long_entry_logic.append(df["global_protections_long_pump"] == True)
          long_entry_logic.append(df["global_protections_long_dump"] == True)

          long_entry_logic.append(df["RSI_3_1h"] <= 95.0)
          long_entry_logic.append(df["RSI_3_4h"] <= 80.0)
          long_entry_logic.append(df["RSI_3_1d"] <= 80.0)
          long_entry_logic.append(df["RSI_14_1h"] < 80.0)
          long_entry_logic.append(df["RSI_14_4h"] < 80.0)
          long_entry_logic.append(df["RSI_14_1d"] < 90.0)
          long_entry_logic.append(df["OBV_change_pct"] > -5.0)
          long_entry_logic.append(df["OBV_change_pct_15m"] > -10.0)
          long_entry_logic.append(df["OBV_change_pct_1h"] > -40.0)
          long_entry_logic.append((df["RSI_3"] > 4.0) | (df["change_pct"] > -4.0))
          long_entry_logic.append((df["RSI_3_15m"] > 6.0) | (df["change_pct_15m"] > -6.0))
          long_entry_logic.append((df["RSI_3_1h"] > 12.0) | (df["change_pct_1h"] > -8.0))
          long_entry_logic.append((df["RSI_3_4h"] > 12.0) | (df["change_pct_4h"] > -10.0))
          long_entry_logic.append((df["RSI_3_1h"] > 4.0) | (df["RSI_14_1h"] > 25.0))
          long_entry_logic.append(
            (df["BBB_20_2.0_4h"] < 50.0)
            | (df["MFI_14_4h"] < 30.0)
            | (df["RSI_14_4h"] < 30.0)
            | (df["change_pct_4h"] > -8.0)
          )
          long_entry_logic.append(
            (df["RSI_3_15m"] > 10.0)
            | (df["RSI_14_15m"] < 30.0)
            | (df["MFI_14_15m"] < 30.0)
            | (df["AROONU_14_15m"] < 25.0)
            | (df["change_pct_15m"] > -4.0)
          )
          long_entry_logic.append(
            (df["RSI_3_1h"] > 25.0)
            | (df["RSI_14_1h"] < 30.0)
            | (df["MFI_14_1h"] < 30.0)
            | (df["AROONU_14_1h"] < 25.0)
            | (df["AROOND_14_1h"] == 100.0)
            | (df["change_pct_1h"] > -4.0)
          )
          long_entry_logic.append(
            (df["RSI_3_1h"] > 25.0)
            | (df["RSI_14_1h"] < 30.0)
            | (df["MFI_14_1h"] < 30.0)
            | (df["AROONU_14_1h"] < 25.0)
            | (df["change_pct_1h"] > -8.0)
          )
          long_entry_logic.append((df["RSI_3_4h"] < 70.0) | (df["change_pct_4h"] < 20.0))
          long_entry_logic.append((df["RSI_3_1d"] < 70.0) | (df["change_pct_1d"] < 30.0))

          # Logic
          long_entry_logic.append(df["RSI_14"] > 5.0)
          long_entry_logic.append(df["WILLR_14"] < -90.0)
          long_entry_logic.append(df["AROONU_14"] < 25.0)
          long_entry_logic.append(df["close"] < (df["EMA_20"] * 0.942))

        # Condition #3 - Normal mode (Long).
        if index == 3:
          # Protections
          long_entry_logic.append(df["protections_long_global"] == True)
          long_entry_logic.append(df["global_protections_long_pump"] == True)
          long_entry_logic.append(df["global_protections_long_dump"] == True)

          long_entry_logic.append(df["RSI_3_1h"] >= 12.0)
          long_entry_logic.append(df["RSI_3_1h"] <= 85.0)
          long_entry_logic.append(df["RSI_3_4h"] >= 12.0)
          long_entry_logic.append(df["RSI_3_4h"] <= 85.0)
          long_entry_logic.append(df["RSI_3_1d"] >= 12.0)
          long_entry_logic.append(df["RSI_3_1d"] <= 85.0)
          long_entry_logic.append(df["RSI_14_1h"] < 85.0)
          long_entry_logic.append(df["RSI_14_4h"] < 85.0)
          long_entry_logic.append(df["RSI_14_1d"] < 90.0)

          # Logic
          long_entry_logic.append(df["RSI_20"] < df["RSI_20"].shift(1))
          long_entry_logic.append(df["RSI_4"] < 46.0)
          long_entry_logic.append(df["CTI_20"] < -0.5)
          long_entry_logic.append(df["close"] < df["SMA_16"] * 0.942)
          long_entry_logic.append(df["AROONU_14"] < 25.0)
          long_entry_logic.append(df["AROONU_14_15m"] < 25.0)

        # Condition #41 - Quick mode (Long).
        if index == 41:
          long_entry_logic.append(df["RSI_3"] >= 2.0)
          long_entry_logic.append(df["RSI_3"] <= 60.0)
          long_entry_logic.append(df["RSI_3_15m"] >= 6.0)
          long_entry_logic.append(df["RSI_3_1h"] >= 10.0)
          long_entry_logic.append(df["RSI_3_4h"] >= 10.0)
          long_entry_logic.append(df["RSI_14_1d"] < 70.0)
          long_entry_logic.append(df["CTI_20_1h"] < 0.75)
          long_entry_logic.append(df["CTI_20_4h"] < 0.5)
          long_entry_logic.append(df["WILLR_14_1h"] > -90.0)
          long_entry_logic.append(df["WILLR_14_4h"] > -85.0)

          # Logic
          long_entry_logic.append(df["RSI_14"] < 36.0)
          long_entry_logic.append(df["AROONU_14"] < 25.0)
          long_entry_logic.append(df["AROOND_14"] > 75.0)
          long_entry_logic.append(df["EMA_9"] < (df["EMA_26"] * 0.970))

        # Condition #42 - Quick mode (Long).
        if index == 42:
          long_entry_logic.append(df["RSI_3"] <= 40.0)
          long_entry_logic.append(df["RSI_3_15m"] >= 20.0)
          long_entry_logic.append(df["RSI_14_1h"] < 85.0)
          long_entry_logic.append(df["RSI_14_4h"] < 85.0)
          long_entry_logic.append(df["RSI_14_1d"] < 85.0)

          # Logic
          long_entry_logic.append(df["CTI_20"] < -0.85)
          long_entry_logic.append(df["WILLR_14"] < -50.0)
          long_entry_logic.append(df["CTI_40_1h"] < -0.85)
          long_entry_logic.append(df["WILLR_84_1h"] < -70.0)
          long_entry_logic.append(df["BBB_20_2.0_1h"] > 16.0)
          long_entry_logic.append(df["close_max_48"] >= (df["close"] * 1.10))

        # Condition #43 - Rapid mode (Long).
        if index == 43:
          # Protections
          long_entry_logic.append(df["protections_long_global"] == True)
          long_entry_logic.append(df["global_protections_long_pump"] == True)
          long_entry_logic.append(df["global_protections_long_dump"] == True)

          long_entry_logic.append(df["RSI_14_1h"] < 80.0)
          long_entry_logic.append(df["RSI_14_4h"] < 80.0)
          long_entry_logic.append(df["RSI_14_1d"] < 90.0)
          long_entry_logic.append(df["OBV_change_pct"] > -10.0)
          long_entry_logic.append((df["RSI_3"] > 2.0) | (df["change_pct"] > -5.0))
          long_entry_logic.append((df["RSI_3"] > 4.0) | (df["change_pct"] > -10.0))
          long_entry_logic.append(
            (df["BBB_20_2.0_4h"] < 50.0)
            | (df["MFI_14_4h"] < 30.0)
            | (df["RSI_14_4h"] < 30.0)
            | (df["change_pct_4h"] > -8.0)
          )
          long_entry_logic.append((df["RSI_3_1h"] > 2.0) | (df["CMF_20_1h"] > -0.4))
          long_entry_logic.append((df["RSI_3_15m"] > 4.0) | (df["CMF_20_15m"] > -0.3) | (df["change_pct_1h"] > -8.0))

          # Logic
          long_entry_logic.append(df["RSI_14"] < 40.0)
          long_entry_logic.append(df["MFI_14"] < 40.0)
          long_entry_logic.append(df["AROONU_14"] < 25.0)
          long_entry_logic.append(df["EMA_26"] > df["EMA_12"])
          long_entry_logic.append((df["EMA_26"] - df["EMA_12"]) > (df["open"] * 0.024))
          long_entry_logic.append((df["EMA_26"].shift() - df["EMA_12"].shift()) > (df["open"] / 100.0))
          long_entry_logic.append(df["close"] < (df["EMA_20"] * 0.958))
          long_entry_logic.append(df["close"] < (df["BBL_20_2.0"] * 0.992))

        # Condition #120 - Grind mode (Long).
        if index == 120:
          long_entry_logic.append(num_open_long_grind_mode < self.grind_mode_max_slots)
          long_entry_logic.append(is_pair_long_grind_mode)
          long_entry_logic.append(df["RSI_3"] <= 40.0)
          long_entry_logic.append(df["RSI_3_15m"] >= 20.0)
          long_entry_logic.append(df["RSI_14_1h"] < 85.0)
          long_entry_logic.append(df["RSI_14_4h"] < 85.0)
          long_entry_logic.append(df["RSI_14_1d"] < 85.0)
          long_entry_logic.append(df["close_max_48"] >= (df["close"] * 1.10))

          # Logic
          long_entry_logic.append(df["CTI_20"] < -0.85)
          long_entry_logic.append(df["WILLR_14"] < -80.0)
          long_entry_logic.append(df["AROONU_14"] < 25.0)

        # Long Entry Conditions Ends Here

        long_entry_logic.append(df["volume"] > 0)
        item_long_entry = reduce(lambda x, y: x & y, long_entry_logic)
        df.loc[item_long_entry, "enter_tag"] += f"{index} "
        long_entry_conditions.append(item_long_entry)
        df.loc[:, "enter_long"] = item_long_entry

    if long_entry_conditions:
      df.loc[:, "enter_long"] = reduce(lambda x, y: x | y, long_entry_conditions)

    #   ______  __    __  ______  _______ ________        ________ __    __ ________ ________ _______
    #  /      \|  \  |  \/      \|       |        \      |        |  \  |  |        |        |       \
    # |  $$$$$$| $$  | $|  $$$$$$| $$$$$$$\$$$$$$$$      | $$$$$$$| $$\ | $$\$$$$$$$| $$$$$$$| $$$$$$$\
    # | $$___\$| $$__| $| $$  | $| $$__| $$ | $$         | $$__   | $$$\| $$  | $$  | $$__   | $$__| $$
    #  \$$    \| $$    $| $$  | $| $$    $$ | $$         | $$  \  | $$$$\ $$  | $$  | $$  \  | $$    $$
    #  _\$$$$$$| $$$$$$$| $$  | $| $$$$$$$\ | $$         | $$$$$  | $$\$$ $$  | $$  | $$$$$  | $$$$$$$\
    # |  \__| $| $$  | $| $$__/ $| $$  | $$ | $$         | $$_____| $$ \$$$$  | $$  | $$_____| $$  | $$
    #  \$$    $| $$  | $$\$$    $| $$  | $$ | $$         | $$     | $$  \$$$  | $$  | $$     | $$  | $$
    #   \$$$$$$ \$$   \$$ \$$$$$$ \$$   \$$  \$$          \$$$$$$$$\$$   \$$   \$$   \$$$$$$$$\$$   \$$
    #

    for enabled_short_entry_signal in self.short_entry_signal_params:
      short_index = int(enabled_short_entry_signal.split("_")[3])
      item_short_buy_protection_list = [True]
      if self.short_entry_signal_params[f"{enabled_short_entry_signal}"]:
        # Short Entry Conditions Starts Here
        # -----------------------------------------------------------------------------------------
        short_entry_logic = []
        short_entry_logic.append(reduce(lambda x, y: x & y, item_short_buy_protection_list))

        # Condition #500 - Normal mode (Short).
        if short_index == 500:
          # Protections
          short_entry_logic.append(df["protections_short_global"] == True)
          short_entry_logic.append(df["global_protections_short_pump"] == True)
          short_entry_logic.append(df["global_protections_short_dump"] == True)
          short_entry_logic.append(df["hl_pct_change_6_1h"] < 0.90)
          short_entry_logic.append(df["hl_pct_change_12_1h"] < 1.00)
          short_entry_logic.append(df["num_empty_288"] < allowed_empty_candles)

          short_entry_logic.append(df["RSI_3_15m"] <= 96.0)
          short_entry_logic.append(df["RSI_3_1h"] <= 96.0)

          # Logic
          short_entry_logic.append(df["EMA_12"] > df["EMA_26"])
          short_entry_logic.append((df["EMA_12"] - df["EMA_26"]) > (df["open"] * 0.028))
          short_entry_logic.append((df["EMA_12"] - df["EMA_26"]) > (df["open"] / 100.0))
          short_entry_logic.append(df["close"] > (df["BBU_20_2.0"] * 1.012))
          short_entry_logic.append(df["RSI_14"] > 64.0)

        # Condition #501 - Rapid mode (Short).
        if short_index == 501:
          # Protections
          # short_entry_logic.append(df["global_protections_long_pump"] == False)
          # short_entry_logic.append(df["global_protections_long_dump"] == False)
          # short_entry_logic.append(df["btc_pct_close_max_24_5m"] < 0.03)
          # short_entry_logic.append(df["btc_pct_close_max_72_5m"] < 0.03)

          # Logic
          short_entry_logic.append(df["buy_short2"] > 0)

        # Short Entry Conditions Ends Here

        short_entry_logic.append(df["volume"] > 0)
        item_short_entry = reduce(lambda x, y: x & y, short_entry_logic)
        df.loc[item_short_entry, "enter_tag"] += f"{short_index} "
        short_entry_conditions.append(item_short_entry)
        df.loc[:, "enter_short"] = item_short_entry

    if short_entry_conditions:
      df.loc[:, "enter_short"] = reduce(lambda x, y: x | y, short_entry_conditions)

    return df

  ###############################################################################################

  # COMMON FUNCTIONS FOR BOTH LONG AND SHORT SIDE ENDS HERE

  ###############################################################################################

  #  /$$        /$$$$$$  /$$   /$$  /$$$$$$         /$$$$$$  /$$$$$$ /$$$$$$$  /$$$$$$$$
  # | $$       /$$__  $$| $$$ | $$ /$$__  $$       /$$__  $$|_  $$_/| $$__  $$| $$_____/
  # | $$      | $$  \ $$| $$$$| $$| $$  \__/      | $$  \__/  | $$  | $$  \ $$| $$
  # | $$      | $$  | $$| $$ $$ $$| $$ /$$$$      |  $$$$$$   | $$  | $$  | $$| $$$$$
  # | $$      | $$  | $$| $$  $$$$| $$|_  $$       \____  $$  | $$  | $$  | $$| $$__/
  # | $$      | $$  | $$| $$\  $$$| $$  \ $$       /$$  \ $$  | $$  | $$  | $$| $$
  # | $$$$$$$$|  $$$$$$/| $$ \  $$|  $$$$$$/      |  $$$$$$/ /$$$$$$| $$$$$$$/| $$$$$$$$
  # |________/ \______/ |__/  \__/ \______/        \______/ |______/|_______/ |________/

  # Long Side Functions for handling long orders
  # ---------------------------------------------------------------------------------------------

  #
  #  /$$        /$$$$$$  /$$   /$$  /$$$$$$        /$$$$$$$$ /$$   /$$ /$$$$$$ /$$$$$$$$
  # | $$       /$$__  $$| $$$ | $$ /$$__  $$      | $$_____/| $$  / $$|_  $$_/|__  $$__/
  # | $$      | $$  \ $$| $$$$| $$| $$  \__/      | $$      |  $$/ $$/  | $$     | $$
  # | $$      | $$  | $$| $$ $$ $$| $$ /$$$$      | $$$$$    \  $$$$/   | $$     | $$
  # | $$      | $$  | $$| $$  $$$$| $$|_  $$      | $$__/     >$$  $$   | $$     | $$
  # | $$      | $$  | $$| $$\  $$$| $$  \ $$      | $$       /$$/\  $$  | $$     | $$
  # | $$$$$$$$|  $$$$$$/| $$ \  $$|  $$$$$$/      | $$$$$$$$| $$  \ $$ /$$$$$$   | $$
  # |________/ \______/ |__/  \__/ \______/       |________/|__/  |__/|______/   |__/
  #

  ###############################################################################################

  # LONG EXIT FUNCTIONS STARTS HERE

  ###############################################################################################

  # Long Exit Normal
  # ---------------------------------------------------------------------------------------------
  def long_exit_normal(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.long_exit_signals(
      self.long_normal_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.long_exit_main(
        self.long_normal_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.long_exit_williams_r(
        self.long_normal_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.long_exit_dec(
        self.long_normal_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.long_exit_stoploss(
        self.long_normal_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_normal_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_normal_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_normal_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.long_normal_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_normal_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_normal_mode_name}_stoploss_doom",
        f"exit_{self.long_normal_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.005:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.long_normal_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.long_normal_mode_name}_max",
      # f"exit_{self.long_normal_mode_name}_stoploss_doom",
      # f"exit_{self.long_normal_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Long Exit Pump
  # ---------------------------------------------------------------------------------------------
  def long_exit_pump(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.long_exit_signals(
      self.long_pump_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.long_exit_main(
        self.long_pump_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.long_exit_williams_r(
        self.long_pump_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.long_exit_dec(
        self.long_pump_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.long_exit_stoploss(
        self.long_pump_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_pump_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_pump_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_pump_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.long_pump_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_pump_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_pump_mode_name}_stoploss_doom",
        f"exit_{self.long_pump_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_pump_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_pump_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.005:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.long_pump_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.long_pump_mode_name}_max",
      # f"exit_{self.long_pump_mode_name}_stoploss_doom",
      # f"exit_{self.long_pump_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Long Exit Signals
  # ---------------------------------------------------------------------------------------------
  def long_exit_quick(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.long_exit_signals(
      self.long_quick_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.long_exit_main(
        self.long_quick_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.long_exit_williams_r(
        self.long_quick_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.long_exit_dec(
        self.long_quick_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.long_exit_stoploss(
        self.long_quick_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Extra sell logic
    if not sell:
      if (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_14"] > 78.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_1"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["MFI_14"] > 84.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_2"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["WILLR_14"] >= -0.1):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_3"
      elif (
        (0.09 >= profit_init_ratio > 0.02)
        and (last_candle["RSI_14"] >= 72.0)
        and (last_candle["RSI_3"] > 90.0)
        and (last_candle["RSI_3_15m"] > 90.0)
      ):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_4"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_3_15m"] > 96.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_5"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_3"] > 85.0) and (last_candle["RSI_3_15m"] > 85.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_6"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_3"] > 90.0) and (last_candle["RSI_3_15m"] > 80.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_7"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_3"] > 92.0) and (last_candle["RSI_3_15m"] > 75.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_8"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_3"] > 94.0) and (last_candle["RSI_3_15m"] > 70.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_9"
      elif (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_3"] > 99.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_q_10"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_quick_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_quick_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.001):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_quick_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.long_quick_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_quick_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_quick_mode_name}_stoploss_doom",
        f"exit_{self.long_quick_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_quick_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_quick_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.005:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.long_quick_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.long_quick_mode_name}_max",
      # f"exit_{self.long_quick_mode_name}_stoploss_doom",
      # f"exit_{self.long_quick_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Long Exit Rebuy
  # ---------------------------------------------------------------------------------------------
  def long_exit_rebuy(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]
    sell = False

    # Original sell signals
    sell, signal_name = self.long_exit_signals(
      self.long_rebuy_mode_name,
      profit_current_stake_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.long_exit_main(
        self.long_rebuy_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.long_exit_williams_r(
        self.long_rebuy_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.long_exit_dec(
        self.long_rebuy_mode_name,
        profit_current_stake_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      if (
        profit_stake
        < -(
          filled_entries[0].cost
          * (self.stop_threshold_futures_rebuy if self.is_futures_mode else self.stop_threshold_spot_rebuy)
          # / (trade.leverage if self.is_futures_mode else 1.0)
        )
        # temporary
        and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
      ):
        sell, signal_name = True, f"exit_{self.long_rebuy_mode_name}_stoploss_doom"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_rebuy_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_rebuy_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.001):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_rebuy_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.long_rebuy_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rebuy_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_rebuy_mode_name}_stoploss_doom",
        f"exit_{self.long_rebuy_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rebuy_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rebuy_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.005:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.long_rebuy_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [f"exit_profit_{self.long_rebuy_mode_name}_max"]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Long Exit High Profit
  # ---------------------------------------------------------------------------------------------
  def long_exit_high_profit(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.long_exit_signals(
      self.long_high_profit_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.long_exit_main(
        self.long_high_profit_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.long_exit_williams_r(
        self.long_high_profit_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.long_exit_stoploss(
        self.long_high_profit_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_high_profit_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_high_profit_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.001):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_high_profit_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.long_high_profit_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_high_profit_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_high_profit_mode_name}_stoploss_doom",
        f"exit_{self.long_high_profit_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_high_profit_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_high_profit_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.03:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.long_high_profit_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.long_high_profit_mode_name}_max",
      # f"exit_{self.long_high_profit_mode_name}_stoploss_doom",
      # f"exit_{self.long_high_profit_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Long Exit Rapid
  # ---------------------------------------------------------------------------------------------
  def long_exit_rapid(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]
    sell = False

    # Original sell signals
    sell, signal_name = self.long_exit_signals(
      self.long_rapid_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.long_exit_main(
        self.long_rapid_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.long_exit_williams_r(
        self.long_rapid_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.long_exit_dec(
        self.long_rapid_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.long_exit_stoploss(
        self.long_rapid_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Extra sell logic
    if not sell:
      if (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_14"] > 78.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_1"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["MFI_14"] > 84.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_2"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["WILLR_14"] >= -0.1):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_3"
      elif (
        (0.09 >= profit_init_ratio > 0.005)
        and (last_candle["RSI_14"] >= 72.0)
        and (last_candle["RSI_3"] > 90.0)
        and (last_candle["RSI_3_15m"] > 90.0)
      ):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_4"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_3_15m"] > 96.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_5"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_3"] > 85.0) and (last_candle["RSI_3_15m"] > 85.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_6"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_3"] > 90.0) and (last_candle["RSI_3_15m"] > 80.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_7"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_3"] > 92.0) and (last_candle["RSI_3_15m"] > 75.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_8"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_3"] > 94.0) and (last_candle["RSI_3_15m"] > 70.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_9"
      elif (0.09 >= profit_init_ratio > 0.005) and (last_candle["RSI_3"] > 99.0):
        sell, signal_name = True, f"exit_{self.long_quick_mode_name}_rpd_10"

      # Stoplosses
      if (
        (
          profit_stake
          < -(
            filled_entries[0].cost
            * (self.stop_threshold_rapid_futures if self.is_futures_mode else self.stop_threshold_rapid_spot)
            # / (trade.leverage if self.is_futures_mode else 1.0)
          )
        )
        # temporary
        and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
      ):
        sell, signal_name = True, f"exit_{self.long_rapid_mode_name}_stoploss_doom"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.long_rapid_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.long_rapid_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.long_rapid_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.long_rapid_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rapid_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.long_rapid_mode_name}_stoploss_doom",
        f"exit_{self.long_rapid_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rapid_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.long_rapid_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.005:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.long_rapid_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [f"exit_profit_{self.long_rapid_mode_name}_max"]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Long Exit Grind
  # ---------------------------------------------------------------------------------------------
  def long_exit_grind(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    if profit_init_ratio > 0.25:
      return True, f"exit_{self.long_grind_mode_name}_g"
    return False, None

  # Long Exit Signals
  # ---------------------------------------------------------------------------------------------
  def long_exit_signals(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    # Sell signal 1
    if (
      (last_candle["RSI_14"] > 84.0)
      and (last_candle["close"] > last_candle["BBU_20_2.0"])
      and (previous_candle_1["close"] > previous_candle_1["BBU_20_2.0"])
      and (previous_candle_2["close"] > previous_candle_2["BBU_20_2.0"])
      and (previous_candle_3["close"] > previous_candle_3["BBU_20_2.0"])
      and (previous_candle_4["close"] > previous_candle_4["BBU_20_2.0"])
    ):
      if last_candle["close"] > last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_2_1"

    # Sell signal 2
    elif (
      (last_candle["RSI_14"] > 86.0)
      and (last_candle["close"] > last_candle["BBU_20_2.0"])
      and (previous_candle_1["close"] > previous_candle_1["BBU_20_2.0"])
      and (previous_candle_2["close"] > previous_candle_2["BBU_20_2.0"])
    ):
      if last_candle["close"] > last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_2_1"

    # Sell signal 3
    elif last_candle["RSI_14"] > 88.0:
      if last_candle["close"] > last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_2_1"

    # Sell signal 4
    elif (last_candle["RSI_14"] > 84.0) and (last_candle["RSI_14_1h"] > 80.0):
      if last_candle["close"] > last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_4_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_4_2_1"

    # Sell signal 6
    elif (
      (last_candle["close"] < last_candle["EMA_200"])
      and (last_candle["close"] > last_candle["EMA_50"])
      and (last_candle["RSI_14"] > 79.0)
    ):
      if current_profit > 0.01:
        return True, f"exit_{mode_name}_6_1"

    # # Sell signal 7
    # elif (last_candle["RSI_14_1h"] > 79.0) and (last_candle["crossed_below_EMA_12_26"]):
    #   if last_candle["close"] > last_candle["EMA_200"]:
    #     if current_profit > 0.01:
    #       return True, f"exit_{mode_name}_7_1_1"
    #   else:
    #     if current_profit > 0.01:
    #       return True, f"exit_{mode_name}_7_2_1"

    # Sell signal 8
    elif last_candle["close"] > last_candle["BBU_20_2.0_1h"] * 1.14:
      if last_candle["close"] > last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_8_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_8_2_1"

    return False, None

  # Long Exit Main
  # ---------------------------------------------------------------------------------------------
  def long_exit_main(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if last_candle["close"] > last_candle["EMA_200"]:
      if 0.01 > current_profit >= 0.001:
        if last_candle["RSI_14"] < 10.0:
          return True, f"exit_{mode_name}_o_0"
      elif 0.02 > current_profit >= 0.01:
        if last_candle["RSI_14"] < 28.0:
          return True, f"exit_{mode_name}_o_1"
      elif 0.03 > current_profit >= 0.02:
        if last_candle["RSI_14"] < 30.0:
          return True, f"exit_{mode_name}_o_2"
      elif 0.04 > current_profit >= 0.03:
        if last_candle["RSI_14"] < 32.0:
          return True, f"exit_{mode_name}_o_3"
      elif 0.05 > current_profit >= 0.04:
        if last_candle["RSI_14"] < 34.0:
          return True, f"exit_{mode_name}_o_4"
      elif 0.06 > current_profit >= 0.05:
        if last_candle["RSI_14"] < 36.0:
          return True, f"exit_{mode_name}_o_5"
      elif 0.07 > current_profit >= 0.06:
        if last_candle["RSI_14"] < 38.0:
          return True, f"exit_{mode_name}_o_6"
      elif 0.08 > current_profit >= 0.07:
        if last_candle["RSI_14"] < 40.0:
          return True, f"exit_{mode_name}_o_7"
      elif 0.09 > current_profit >= 0.08:
        if last_candle["RSI_14"] < 42.0:
          return True, f"exit_{mode_name}_o_8"
      elif 0.1 > current_profit >= 0.09:
        if last_candle["RSI_14"] < 44.0:
          return True, f"exit_{mode_name}_o_9"
      elif 0.12 > current_profit >= 0.1:
        if last_candle["RSI_14"] < 46.0:
          return True, f"exit_{mode_name}_o_10"
      elif 0.2 > current_profit >= 0.12:
        if last_candle["RSI_14"] < 44.0:
          return True, f"exit_{mode_name}_o_11"
      elif current_profit >= 0.2:
        if last_candle["RSI_14"] < 42.0:
          return True, f"exit_{mode_name}_o_12"
    elif last_candle["close"] < last_candle["EMA_200"]:
      if 0.01 > current_profit >= 0.001:
        if last_candle["RSI_14"] < 12.0:
          return True, f"exit_{mode_name}_u_0"
      elif 0.02 > current_profit >= 0.01:
        if last_candle["RSI_14"] < 30.0:
          return True, f"exit_{mode_name}_u_1"
      elif 0.03 > current_profit >= 0.02:
        if last_candle["RSI_14"] < 32.0:
          return True, f"exit_{mode_name}_u_2"
      elif 0.04 > current_profit >= 0.03:
        if last_candle["RSI_14"] < 34.0:
          return True, f"exit_{mode_name}_u_3"
      elif 0.05 > current_profit >= 0.04:
        if last_candle["RSI_14"] < 36.0:
          return True, f"exit_{mode_name}_u_4"
      elif 0.06 > current_profit >= 0.05:
        if last_candle["RSI_14"] < 38.0:
          return True, f"exit_{mode_name}_u_5"
      elif 0.07 > current_profit >= 0.06:
        if last_candle["RSI_14"] < 40.0:
          return True, f"exit_{mode_name}_u_6"
      elif 0.08 > current_profit >= 0.07:
        if last_candle["RSI_14"] < 42.0:
          return True, f"exit_{mode_name}_u_7"
      elif 0.09 > current_profit >= 0.08:
        if last_candle["RSI_14"] < 44.0:
          return True, f"exit_{mode_name}_u_8"
      elif 0.1 > current_profit >= 0.09:
        if last_candle["RSI_14"] < 46.0:
          return True, f"exit_{mode_name}_u_9"
      elif 0.12 > current_profit >= 0.1:
        if last_candle["RSI_14"] < 48.0:
          return True, f"exit_{mode_name}_u_10"
      elif 0.2 > current_profit >= 0.12:
        if last_candle["RSI_14"] < 46.0:
          return True, f"exit_{mode_name}_u_11"
      elif current_profit >= 0.2:
        if last_candle["RSI_14"] < 44.0:
          return True, f"exit_{mode_name}_u_12"

    return False, None

  # Long Exit Williams R
  # ---------------------------------------------------------------------------------------------
  def long_exit_williams_r(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if 0.01 > current_profit >= 0.001:
      if (last_candle["WILLR_480"] > -0.1) and (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 75.0):
        return True, f"exit_{mode_name}_w_0_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 84.0):
        return True, f"exit_{mode_name}_w_0_2"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] < 40.0):
        return True, f"exit_{mode_name}_w_0_3"
    elif 0.02 > current_profit >= 0.01:
      if last_candle["WILLR_480"] > -0.2:
        return True, f"exit_{mode_name}_w_1_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 78.0):
        return True, f"exit_{mode_name}_w_1_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 46.0):
        return True, f"exit_{mode_name}_w_1_3"
    elif 0.03 > current_profit >= 0.02:
      if last_candle["WILLR_480"] > -0.3:
        return True, f"exit_{mode_name}_w_2_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 77.0):
        return True, f"exit_{mode_name}_w_2_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 48.0):
        return True, f"exit_{mode_name}_w_2_3"
    elif 0.04 > current_profit >= 0.03:
      if last_candle["WILLR_480"] > -0.4:
        return True, f"exit_{mode_name}_w_3_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 76.0):
        return True, f"exit_{mode_name}_w_3_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 50.0):
        return True, f"exit_{mode_name}_w_3_3"
    elif 0.05 > current_profit >= 0.04:
      if last_candle["WILLR_480"] > -0.5:
        return True, f"exit_{mode_name}_w_4_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 75.0):
        return True, f"exit_{mode_name}_w_4_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 52.0):
        return True, f"exit_{mode_name}_w_4_3"
    elif 0.06 > current_profit >= 0.05:
      if last_candle["WILLR_480"] > -0.6:
        return True, f"exit_{mode_name}_w_5_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 74.0):
        return True, f"exit_{mode_name}_w_5_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 54.0):
        return True, f"exit_{mode_name}_w_5_3"
    elif 0.07 > current_profit >= 0.06:
      if last_candle["WILLR_480"] > -0.7:
        return True, f"exit_{mode_name}_w_6_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 75.0):
        return True, f"exit_{mode_name}_w_6_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 52.0):
        return True, f"exit_{mode_name}_w_6_3"
    elif 0.08 > current_profit >= 0.07:
      if last_candle["WILLR_480"] > -0.8:
        return True, f"exit_{mode_name}_w_7_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 76.0):
        return True, f"exit_{mode_name}_w_7_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 50.0):
        return True, f"exit_{mode_name}_w_7_3"
    elif 0.09 > current_profit >= 0.08:
      if last_candle["WILLR_480"] > -0.9:
        return True, f"exit_{mode_name}_w_8_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 77.0):
        return True, f"exit_{mode_name}_w_8_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 48.0):
        return True, f"exit_{mode_name}_w_8_3"
    elif 0.1 > current_profit >= 0.09:
      if last_candle["WILLR_480"] > -1.0:
        return True, f"exit_{mode_name}_w_9_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 78.0):
        return True, f"exit_{mode_name}_w_9_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 46.0):
        return True, f"exit_{mode_name}_w_9_3"
    elif 0.12 > current_profit >= 0.1:
      if last_candle["WILLR_480"] > -1.1:
        return True, f"exit_{mode_name}_w_10_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 79.0):
        return True, f"exit_{mode_name}_w_10_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 44.0):
        return True, f"exit_{mode_name}_w_10_3"
    elif 0.2 > current_profit >= 0.12:
      if last_candle["WILLR_480"] > -0.4:
        return True, f"exit_{mode_name}_w_11_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 80.0):
        return True, f"exit_{mode_name}_w_11_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 42.0):
        return True, f"exit_{mode_name}_w_11_3"
    elif current_profit >= 0.2:
      if last_candle["WILLR_480"] > -0.2:
        return True, f"exit_{mode_name}_w_12_1"
      elif (last_candle["WILLR_14"] >= -1.0) and (last_candle["RSI_14"] > 81.0):
        return True, f"exit_{mode_name}_w_12_2"
      elif (last_candle["WILLR_14"] >= -2.0) and (last_candle["RSI_14"] < 40.0):
        return True, f"exit_{mode_name}_w_12_3"

    return False, None

  # Long Exit Dec
  # ---------------------------------------------------------------------------------------------
  def long_exit_dec(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if 0.01 > current_profit >= 0.001:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_0_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_0_2"
    elif 0.02 > current_profit >= 0.01:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_1_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 68.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_1_2"
    elif 0.03 > current_profit >= 0.02:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_2_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 66.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_2_2"
    elif 0.04 > current_profit >= 0.03:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_3_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 64.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_3_2"
    elif 0.05 > current_profit >= 0.04:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_4_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 62.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_4_2"
    elif 0.06 > current_profit >= 0.05:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_5_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 60.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_5_2"
    elif 0.07 > current_profit >= 0.06:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_6_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 62.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_6_2"
    elif 0.08 > current_profit >= 0.07:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_7_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 64.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_7_2"
    elif 0.09 > current_profit >= 0.08:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_8_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 66.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_8_2"
    elif 0.1 > current_profit >= 0.09:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_9_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 68.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_9_2"
    elif 0.12 > current_profit >= 0.1:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_10_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 70.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_10_2"
    elif 0.2 > current_profit >= 0.12:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_11_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 74.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_11_2"
    elif current_profit >= 0.2:
      if (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] < last_candle["KSTs_9_1h"])
        and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] < last_candle["KSTs_9_4h"])
      ):
        return True, f"exit_{mode_name}_d_12_1"
      elif (
        (last_candle["WILLR_14"] > -1.0)
        and (last_candle["RSI_14"] > 78.0)
        and (last_candle["CMF_20_1h"] < -0.0)
        and (last_candle["EMA_12_1h"] < last_candle["EMA_200_1h"])
        and (last_candle["EMA_12_4h"] < last_candle["EMA_200_4h"])
      ):
        return True, f"exit_{mode_name}_d_12_2"

    return False, None

  # Long Exit Stop Loss
  # ---------------------------------------------------------------------------------------------
  def long_exit_stoploss(
    self,
    mode_name: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]
    # Stoploss doom
    if (
      profit_stake
      < -(
        filled_entries[0].cost
        * (self.stop_threshold_doom_futures if self.is_futures_mode else self.stop_threshold_doom_spot)
        # / trade.leverage
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      return True, f"exit_{mode_name}_stoploss_doom"

    # Stoploss u_e
    if (
      profit_stake
      < -(
        filled_entries[0].cost * (self.stop_threshold_futures if self.is_futures_mode else self.stop_threshold_spot)
        # / trade.leverage
      )
      and (last_candle["close"] < last_candle["EMA_200"])
      and (last_candle["CMF_20"] < -0.0)
      and (((last_candle["EMA_200"] - last_candle["close"]) / last_candle["close"]) < 0.010)
      and (last_candle["RSI_14"] > previous_candle_1["RSI_14"])
      and (last_candle["RSI_14"] > (last_candle["RSI_14_1h"] + 16.0))
      and (current_time - timedelta(minutes=720) > trade.open_date_utc)
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      return True, f"exit_{mode_name}_stoploss_u_e"

    return False, None

  ###############################################################################################
  # LONG EXIT FUNCTIONS ENDS HERE
  ###############################################################################################

  #
  #  /$$       /$$$$$$ /$$   /$$ /$$$$$$         /$$$$$$ /$$$$$$$ /$$$$$$/$$   /$$/$$$$$$$
  # | $$      /$$__  $| $$$ | $$/$$__  $$       /$$__  $| $$__  $|_  $$_| $$$ | $| $$__  $$
  # | $$     | $$  \ $| $$$$| $| $$  \__/      | $$  \__| $$  \ $$ | $$ | $$$$| $| $$  \ $$
  # | $$     | $$  | $| $$ $$ $| $$ /$$$$      | $$ /$$$| $$$$$$$/ | $$ | $$ $$ $| $$  | $$
  # | $$     | $$  | $| $$  $$$| $$|_  $$      | $$|_  $| $$__  $$ | $$ | $$  $$$| $$  | $$
  # | $$     | $$  | $| $$\  $$| $$  \ $$      | $$  \ $| $$  \ $$ | $$ | $$\  $$| $$  | $$
  # | $$$$$$$|  $$$$$$| $$ \  $|  $$$$$$/      |  $$$$$$| $$  | $$/$$$$$| $$ \  $| $$$$$$$/
  # |________/\______/|__/  \__/\______/        \______/|__/  |__|______|__/  \__|_______/
  #

  # Long Grinding Adjust Trade Position
  # ---------------------------------------------------------------------------------------------
  def long_grind_adjust_trade_position(
    self,
    trade: Trade,
    enter_tags,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ):
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]
    # min/max stakes include leverage. The return amounts is before leverage.
    min_stake /= trade.leverage
    max_stake /= trade.leverage
    df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
    if len(df) < 2:
      return None
    last_candle = df.iloc[-1].squeeze()
    previous_candle = df.iloc[-2].squeeze()

    filled_orders = trade.select_filled_orders()
    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)
    count_of_entries = trade.nr_of_successful_entries
    count_of_exits = trade.nr_of_successful_exits

    if count_of_entries == 0:
      return None

    if len(filled_orders) < 1:
      return None
    has_order_tags = False
    if hasattr(filled_orders[0], "ft_order_tag"):
      has_order_tags = True

    exit_rate = current_rate
    if self.dp.runmode.value in ("live", "dry_run"):
      ticker = self.dp.ticker(trade.pair)
      if ("bid" in ticker) and ("ask" in ticker):
        if trade.is_short:
          if self.config["exit_pricing"]["price_side"] in ["ask", "other"]:
            if ticker["ask"] is not None:
              exit_rate = ticker["ask"]
        else:
          if self.config["exit_pricing"]["price_side"] in ["bid", "other"]:
            if ticker["bid"] is not None:
              exit_rate = ticker["bid"]

    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, exit_rate
    )

    slice_amount = filled_entries[0].cost
    slice_profit = (exit_rate - filled_orders[-1].safe_price) / filled_orders[-1].safe_price
    slice_profit_entry = (exit_rate - filled_entries[-1].safe_price) / filled_entries[-1].safe_price
    slice_profit_exit = (
      ((exit_rate - filled_exits[-1].safe_price) / filled_exits[-1].safe_price) if count_of_exits > 0 else 0.0
    )

    current_stake_amount = trade.amount * current_rate
    is_derisk = trade.amount < (filled_entries[0].safe_filled * 0.95)
    is_derisk_calc = False
    is_rebuy_mode = all(c in self.long_rebuy_mode_tags for c in enter_tags) or (
      any(c in self.long_rebuy_mode_tags for c in enter_tags)
      and all(c in (self.long_rebuy_mode_tags + self.long_grind_mode_tags) for c in enter_tags)
    )
    is_grind_mode = all(c in self.long_grind_mode_tags for c in enter_tags)

    fee_open_rate = trade.fee_open if self.custom_fee_open_rate is None else self.custom_fee_open_rate
    fee_close_rate = trade.fee_close if self.custom_fee_close_rate is None else self.custom_fee_close_rate

    # Rebuy mode
    if is_rebuy_mode:
      slice_amount /= self.rebuy_mode_stake_multiplier
    # Grind mode
    elif is_grind_mode:
      slice_amount /= (
        self.grind_mode_stake_multiplier_futures[0]
        if self.is_futures_mode
        else self.grind_mode_stake_multiplier_spot[0]
      )
    elif not is_derisk and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 2, 5) or is_backtest):
      rebuy_stake, order_tag, is_derisk_calc = self.long_adjust_trade_position_no_derisk(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
        last_candle,
        previous_candle,
        filled_orders,
        filled_entries,
        filled_exits,
        exit_rate,
        slice_amount,
        slice_profit_entry,
        slice_profit,
        profit_ratio,
        profit_stake,
        profit_init_ratio,
        current_stake_amount,
        has_order_tags,
      )
      if rebuy_stake is not None:
        if has_order_tags:
          return rebuy_stake, order_tag
        else:
          return rebuy_stake
      elif count_of_exits == 0:
        return None
      elif not is_derisk_calc:
        return None

    if not is_rebuy_mode and not is_grind_mode:
      # First entry is lower now, therefore the grinds must adjust
      if trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest:
        slice_amount /= (
          self.regular_mode_stake_multiplier_futures[0]
          if self.is_futures_mode
          else self.regular_mode_stake_multiplier_spot[0]
        )

    grind_1_max_sub_grinds = 0
    grind_1_stakes = self.grind_1_stakes_futures.copy() if self.is_futures_mode else self.grind_1_stakes_spot.copy()
    grind_1_sub_thresholds = (
      self.grind_1_sub_thresholds_futures if self.is_futures_mode else self.grind_1_sub_thresholds_spot
    )
    if (slice_amount * grind_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_1_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_1_stakes):
        grind_1_stakes[i] *= multi
    grind_1_max_sub_grinds = len(grind_1_stakes)
    grind_1_stop_grinds = self.grind_1_stop_grinds_futures if self.is_futures_mode else self.grind_1_stop_grinds_spot
    grind_1_profit_threshold = (
      self.grind_1_profit_threshold_futures if self.is_futures_mode else self.grind_1_profit_threshold_spot
    )

    grind_2_max_sub_grinds = 0
    grind_2_stakes = self.grind_2_stakes_futures.copy() if self.is_futures_mode else self.grind_2_stakes_spot.copy()
    grind_2_sub_thresholds = (
      self.grind_2_sub_thresholds_futures if self.is_futures_mode else self.grind_2_sub_thresholds_spot
    )
    if (slice_amount * grind_2_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_2_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_2_stakes):
        grind_2_stakes[i] *= multi
    grind_2_max_sub_grinds = len(grind_2_stakes)
    grind_2_stop_grinds = self.grind_2_stop_grinds_futures if self.is_futures_mode else self.grind_2_stop_grinds_spot
    grind_2_profit_threshold = (
      self.grind_2_profit_threshold_futures if self.is_futures_mode else self.grind_2_profit_threshold_spot
    )

    grind_3_max_sub_grinds = 0
    grind_3_stakes = self.grind_3_stakes_futures.copy() if self.is_futures_mode else self.grind_3_stakes_spot.copy()
    grind_3_sub_thresholds = (
      self.grind_3_sub_thresholds_futures if self.is_futures_mode else self.grind_3_sub_thresholds_spot
    )
    if (slice_amount * grind_3_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_3_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_3_stakes):
        grind_3_stakes[i] *= multi
    grind_3_max_sub_grinds = len(grind_3_stakes)
    grind_3_stop_grinds = self.grind_3_stop_grinds_futures if self.is_futures_mode else self.grind_3_stop_grinds_spot
    grind_3_profit_threshold = (
      self.grind_3_profit_threshold_futures if self.is_futures_mode else self.grind_3_profit_threshold_spot
    )

    grind_4_max_sub_grinds = 0
    grind_4_stakes = self.grind_4_stakes_futures.copy() if self.is_futures_mode else self.grind_4_stakes_spot.copy()
    grind_4_sub_thresholds = (
      self.grind_4_sub_thresholds_futures if self.is_futures_mode else self.grind_4_sub_thresholds_spot
    )
    if (slice_amount * grind_4_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_4_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_4_stakes):
        grind_4_stakes[i] *= multi
    grind_4_max_sub_grinds = len(grind_4_stakes)
    grind_4_stop_grinds = self.grind_4_stop_grinds_futures if self.is_futures_mode else self.grind_4_stop_grinds_spot
    grind_4_profit_threshold = (
      self.grind_4_profit_threshold_futures if self.is_futures_mode else self.grind_4_profit_threshold_spot
    )

    grind_5_max_sub_grinds = 0
    grind_5_stakes = self.grind_5_stakes_futures.copy() if self.is_futures_mode else self.grind_5_stakes_spot.copy()
    grind_5_sub_thresholds = (
      self.grind_5_sub_thresholds_futures if self.is_futures_mode else self.grind_5_sub_thresholds_spot
    )
    if (slice_amount * grind_5_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_5_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_5_stakes):
        grind_5_stakes[i] *= multi
    grind_5_max_sub_grinds = len(grind_5_stakes)
    grind_5_stop_grinds = self.grind_5_stop_grinds_futures if self.is_futures_mode else self.grind_5_stop_grinds_spot
    grind_5_profit_threshold = (
      self.grind_5_profit_threshold_futures if self.is_futures_mode else self.grind_5_profit_threshold_spot
    )

    grind_6_max_sub_grinds = 0
    grind_6_stakes = self.grind_6_stakes_futures.copy() if self.is_futures_mode else self.grind_6_stakes_spot.copy()
    grind_6_sub_thresholds = (
      self.grind_6_sub_thresholds_futures if self.is_futures_mode else self.grind_6_sub_thresholds_spot
    )
    if (slice_amount * grind_6_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_6_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_6_stakes):
        grind_6_stakes[i] *= multi
    grind_6_max_sub_grinds = len(grind_6_stakes)
    grind_6_stop_grinds = self.grind_6_stop_grinds_futures if self.is_futures_mode else self.grind_6_stop_grinds_spot
    grind_6_profit_threshold = (
      self.grind_6_profit_threshold_futures if self.is_futures_mode else self.grind_6_profit_threshold_spot
    )

    grind_1_derisk_1_max_sub_grinds = 0
    grind_1_derisk_1_stakes = (
      self.grind_1_derisk_1_stakes_futures.copy() if self.is_futures_mode else self.grind_1_derisk_1_stakes_spot.copy()
    )
    grind_1_derisk_1_sub_thresholds = (
      self.grind_1_derisk_1_sub_thresholds_futures
      if self.is_futures_mode
      else self.grind_1_derisk_1_sub_thresholds_spot
    )
    if (slice_amount * grind_1_derisk_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_1_derisk_1_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_1_derisk_1_stakes):
        grind_1_derisk_1_stakes[i] *= multi
    grind_1_derisk_1_max_sub_grinds = len(grind_1_derisk_1_stakes)
    grind_1_derisk_1_stop_grinds = (
      self.grind_1_derisk_1_stop_grinds_futures if self.is_futures_mode else self.grind_1_derisk_1_stop_grinds_spot
    )
    grind_1_derisk_1_profit_threshold = (
      self.grind_1_derisk_1_profit_threshold_futures
      if self.is_futures_mode
      else self.grind_1_derisk_1_profit_threshold_spot
    )

    grind_2_derisk_1_max_sub_grinds = 0
    grind_2_derisk_1_stakes = (
      self.grind_2_derisk_1_stakes_futures.copy() if self.is_futures_mode else self.grind_2_derisk_1_stakes_spot.copy()
    )
    grind_2_derisk_1_sub_thresholds = (
      self.grind_2_derisk_1_sub_thresholds_futures
      if self.is_futures_mode
      else self.grind_2_derisk_1_sub_thresholds_spot
    )
    if (slice_amount * grind_2_derisk_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_2_derisk_1_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_2_derisk_1_stakes):
        grind_2_derisk_1_stakes[i] *= multi
    grind_2_derisk_1_max_sub_grinds = len(grind_2_derisk_1_stakes)
    grind_2_derisk_1_stop_grinds = (
      self.grind_2_derisk_1_stop_grinds_futures if self.is_futures_mode else self.grind_2_derisk_1_stop_grinds_spot
    )
    grind_2_derisk_1_profit_threshold = (
      self.grind_2_derisk_1_profit_threshold_futures
      if self.is_futures_mode
      else self.grind_2_derisk_1_profit_threshold_spot
    )

    partial_sell = False
    is_derisk_found = False  # d de-risk
    is_derisk_1 = False
    is_derisk_1_found = False  # d1 de-risk exit
    derisk_1_order = None
    derisk_1_reentry_order = None
    derisk_1_sub_grind_count = 0
    derisk_1_total_amount = 0.0
    derisk_1_total_cost = 0.0
    derisk_1_current_open_rate = 0.0
    derisk_1_current_grind_stake = 0.0
    derisk_1_current_grind_stake_profit = 0.0
    derisk_1_is_sell_found = False
    derisk_1_reentry_found = False
    derisk_1_buy_orders = []
    derisk_1_distance_ratio = 0.0
    grind_1_sub_grind_count = 0
    grind_1_total_amount = 0.0
    grind_1_total_cost = 0.0
    grind_1_current_open_rate = 0.0
    grind_1_current_grind_stake = 0.0
    grind_1_current_grind_stake_profit = 0.0
    grind_1_is_sell_found = False
    grind_1_found = False
    grind_1_buy_orders = []
    grind_1_distance_ratio = 0.0
    grind_2_sub_grind_count = 0
    grind_2_total_amount = 0.0
    grind_2_total_cost = 0.0
    grind_2_current_open_rate = 0.0
    grind_2_current_grind_stake = 0.0
    grind_2_current_grind_stake_profit = 0.0
    grind_2_is_sell_found = False
    grind_2_found = False
    grind_2_buy_orders = []
    grind_2_distance_ratio = 0.0
    grind_3_sub_grind_count = 0
    grind_3_total_amount = 0.0
    grind_3_total_cost = 0.0
    grind_3_current_open_rate = 0.0
    grind_3_current_grind_stake = 0.0
    grind_3_current_grind_stake_profit = 0.0
    grind_3_is_sell_found = False
    grind_3_found = False
    grind_3_buy_orders = []
    grind_3_distance_ratio = 0.0
    grind_4_sub_grind_count = 0
    grind_4_total_amount = 0.0
    grind_4_total_cost = 0.0
    grind_4_current_open_rate = 0.0
    grind_4_current_grind_stake = 0.0
    grind_4_current_grind_stake_profit = 0.0
    grind_4_is_sell_found = False
    grind_4_found = False
    grind_4_buy_orders = []
    grind_4_distance_ratio = 0.0
    grind_5_sub_grind_count = 0
    grind_5_total_amount = 0.0
    grind_5_total_cost = 0.0
    grind_5_current_open_rate = 0.0
    grind_5_current_grind_stake = 0.0
    grind_5_current_grind_stake_profit = 0.0
    grind_5_is_sell_found = False
    grind_5_found = False
    grind_5_buy_orders = []
    grind_5_distance_ratio = 0.0
    grind_6_sub_grind_count = 0
    grind_6_total_amount = 0.0
    grind_6_total_cost = 0.0
    grind_6_current_open_rate = 0.0
    grind_6_current_grind_stake = 0.0
    grind_6_current_grind_stake_profit = 0.0
    grind_6_is_sell_found = False
    grind_6_found = False
    grind_6_buy_orders = []
    grind_6_distance_ratio = 0.0
    grind_1_derisk_1_sub_grind_count = 0
    grind_1_derisk_1_total_amount = 0.0
    grind_1_derisk_1_total_cost = 0.0
    grind_1_derisk_1_current_open_rate = 0.0
    grind_1_derisk_1_current_grind_stake = 0.0
    grind_1_derisk_1_current_grind_stake_profit = 0.0
    grind_1_derisk_1_is_sell_found = False
    grind_1_derisk_1_found = False
    grind_1_derisk_1_buy_orders = []
    grind_1_derisk_1_distance_ratio = 0.0
    grind_2_derisk_1_sub_grind_count = 0
    grind_2_derisk_1_total_amount = 0.0
    grind_2_derisk_1_total_cost = 0.0
    grind_2_derisk_1_current_open_rate = 0.0
    grind_2_derisk_1_current_grind_stake = 0.0
    grind_2_derisk_1_current_grind_stake_profit = 0.0
    grind_2_derisk_1_is_sell_found = False
    grind_2_derisk_1_found = False
    grind_2_derisk_1_buy_orders = []
    grind_2_derisk_1_distance_ratio = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        if not is_derisk_1 and order_tag == "d1":
          derisk_1_sub_grind_count += 1
          derisk_1_total_amount += order.safe_filled
          derisk_1_total_cost += order.safe_filled * order.safe_price
          derisk_1_buy_orders.append(order.id)
          if not derisk_1_reentry_found and not is_derisk_1:
            derisk_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            derisk_1_reentry_found = True
            derisk_1_reentry_order = order
        elif not grind_1_derisk_1_is_sell_found and order_tag == "dl1":
          grind_1_derisk_1_sub_grind_count += 1
          grind_1_derisk_1_total_amount += order.safe_filled
          grind_1_derisk_1_total_cost += order.safe_filled * order.safe_price
          grind_1_derisk_1_buy_orders.append(order.id)
          if not grind_1_derisk_1_found:
            grind_1_derisk_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_1_derisk_1_found = True
        elif not grind_2_derisk_1_is_sell_found and order_tag == "dl2":
          grind_2_derisk_1_sub_grind_count += 1
          grind_2_derisk_1_total_amount += order.safe_filled
          grind_2_derisk_1_total_cost += order.safe_filled * order.safe_price
          grind_2_derisk_1_buy_orders.append(order.id)
          if not grind_2_derisk_1_found:
            grind_2_derisk_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_2_derisk_1_found = True
        elif not grind_6_is_sell_found and order_tag == "gd6":
          grind_6_sub_grind_count += 1
          grind_6_total_amount += order.safe_filled
          grind_6_total_cost += order.safe_filled * order.safe_price
          grind_6_buy_orders.append(order.id)
          if not grind_6_found:
            grind_6_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_6_found = True
        elif not grind_5_is_sell_found and order_tag == "gd5":
          grind_5_sub_grind_count += 1
          grind_5_total_amount += order.safe_filled
          grind_5_total_cost += order.safe_filled * order.safe_price
          grind_5_buy_orders.append(order.id)
          if not grind_5_found:
            grind_5_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_5_found = True
        elif not grind_4_is_sell_found and order_tag == "gd4":
          grind_4_sub_grind_count += 1
          grind_4_total_amount += order.safe_filled
          grind_4_total_cost += order.safe_filled * order.safe_price
          grind_4_buy_orders.append(order.id)
          if not grind_4_found:
            grind_4_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_4_found = True
        elif not grind_3_is_sell_found and order_tag == "gd3":
          grind_3_sub_grind_count += 1
          grind_3_total_amount += order.safe_filled
          grind_3_total_cost += order.safe_filled * order.safe_price
          grind_3_buy_orders.append(order.id)
          if not grind_3_found:
            grind_3_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_3_found = True
        elif not grind_2_is_sell_found and order_tag == "gd2":
          grind_2_sub_grind_count += 1
          grind_2_total_amount += order.safe_filled
          grind_2_total_cost += order.safe_filled * order.safe_price
          grind_2_buy_orders.append(order.id)
          if not grind_2_found:
            grind_2_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_2_found = True
        elif not grind_1_is_sell_found and order_tag not in [
          "r",
          "d1",
          "dl1",
          "dl2",
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "sg1",
          "sg2",
          "sg3",
          "sg4",
          "sg5",
          "sg6",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "gm0",
          "gmd0",
        ]:
          grind_1_sub_grind_count += 1
          grind_1_total_amount += order.safe_filled
          grind_1_total_cost += order.safe_filled * order.safe_price
          grind_1_buy_orders.append(order.id)
          if not grind_1_found:
            grind_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_1_found = True
      elif order.ft_order_side == "sell":
        if (
          order is filled_exits[-1]
          and (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake
        ):
          partial_sell = True
          break
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            sell_order_tag = order.ft_order_tag
            order_mode = sell_order_tag.split(" ", 1)
            if len(order_mode) > 0:
              order_tag = order_mode[0]
        if order_tag in ["dl1", "ddl1"]:
          grind_1_derisk_1_is_sell_found = True
        elif order_tag in ["dl2", "ddl2"]:
          grind_2_derisk_1_is_sell_found = True
        elif order_tag in ["gd6", "dd6"]:
          grind_6_is_sell_found = True
        elif order_tag in ["gd5", "dd5"]:
          grind_5_is_sell_found = True
        if order_tag in ["gd4", "dd4"]:
          grind_4_is_sell_found = True
        elif order_tag in ["gd3", "dd3"]:
          grind_3_is_sell_found = True
        elif order_tag in ["gd2", "dd2"]:
          grind_2_is_sell_found = True
        elif order_tag in ["d1"]:
          if not is_derisk_1_found:
            is_derisk_1_found = True
            is_derisk_1 = True
            derisk_1_order = order
        elif order_tag in ["p", "r", "d", "dd0", "partial_exit", "force_exit", ""]:
          if order_tag in ["d"]:
            is_derisk_found = True
            is_derisk = True
          grind_1_is_sell_found = True
          grind_2_is_sell_found = True
          grind_3_is_sell_found = True
          grind_4_is_sell_found = True
          grind_5_is_sell_found = True
          grind_6_is_sell_found = True
          grind_1_derisk_1_is_sell_found = True
          grind_2_derisk_1_is_sell_found = True
        elif order_tag not in [
          "dl1",
          "ddl1",
          "dl2",
          "ddl2",
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "sg1",
          "sg2",
          "sg3",
          "sg4",
          "sg5",
          "sg6",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "dd2",
          "dd3",
          "dd4",
          "dd5",
          "dd6",
          "gm0",
          "gmd0",
        ]:
          grind_1_is_sell_found = True

    if derisk_1_sub_grind_count > 0:
      derisk_1_current_open_rate = derisk_1_total_cost / derisk_1_total_amount
      derisk_1_current_grind_stake = derisk_1_total_amount * exit_rate * (1 - trade.fee_close)
      derisk_1_current_grind_stake_profit = derisk_1_current_grind_stake - derisk_1_total_cost
    if grind_1_sub_grind_count > 0:
      grind_1_current_open_rate = grind_1_total_cost / grind_1_total_amount
      grind_1_current_grind_stake = grind_1_total_amount * exit_rate * (1 - trade.fee_close)
      grind_1_current_grind_stake_profit = grind_1_current_grind_stake - grind_1_total_cost
    if grind_2_sub_grind_count > 0:
      grind_2_current_open_rate = grind_2_total_cost / grind_2_total_amount
      grind_2_current_grind_stake = grind_2_total_amount * exit_rate * (1 - trade.fee_close)
      grind_2_current_grind_stake_profit = grind_2_current_grind_stake - grind_2_total_cost
    if grind_3_sub_grind_count > 0:
      grind_3_current_open_rate = grind_3_total_cost / grind_3_total_amount
      grind_3_current_grind_stake = grind_3_total_amount * exit_rate * (1 - trade.fee_close)
      grind_3_current_grind_stake_profit = grind_3_current_grind_stake - grind_3_total_cost
    if grind_4_sub_grind_count > 0:
      grind_4_current_open_rate = grind_4_total_cost / grind_4_total_amount
      grind_4_current_grind_stake = grind_4_total_amount * exit_rate * (1 - trade.fee_close)
      grind_4_current_grind_stake_profit = grind_4_current_grind_stake - grind_4_total_cost
    if grind_5_sub_grind_count > 0:
      grind_5_current_open_rate = grind_5_total_cost / grind_5_total_amount
      grind_5_current_grind_stake = grind_5_total_amount * exit_rate * (1 - trade.fee_close)
      grind_5_current_grind_stake_profit = grind_5_current_grind_stake - grind_5_total_cost
    if grind_6_sub_grind_count > 0:
      grind_6_current_open_rate = grind_6_total_cost / grind_6_total_amount
      grind_6_current_grind_stake = grind_6_total_amount * exit_rate * (1 - trade.fee_close)
      grind_6_current_grind_stake_profit = grind_6_current_grind_stake - grind_6_total_cost
    if grind_1_derisk_1_sub_grind_count > 0:
      grind_1_derisk_1_current_open_rate = grind_1_derisk_1_total_cost / grind_1_derisk_1_total_amount
      grind_1_derisk_1_current_grind_stake = grind_1_derisk_1_total_amount * exit_rate * (1 - trade.fee_close)
      grind_1_derisk_1_current_grind_stake_profit = grind_1_derisk_1_current_grind_stake - grind_1_derisk_1_total_cost
    if grind_2_derisk_1_sub_grind_count > 0:
      grind_2_derisk_1_current_open_rate = grind_2_derisk_1_total_cost / grind_2_derisk_1_total_amount
      grind_2_derisk_1_current_grind_stake = grind_2_derisk_1_total_amount * exit_rate * (1 - trade.fee_close)
      grind_2_derisk_1_current_grind_stake_profit = grind_2_derisk_1_current_grind_stake - grind_2_derisk_1_total_cost

    num_open_grinds = (
      grind_1_sub_grind_count
      + grind_2_sub_grind_count
      + grind_3_sub_grind_count
      + grind_4_sub_grind_count
      + grind_5_sub_grind_count
      + grind_6_sub_grind_count
      + grind_1_derisk_1_sub_grind_count
      + grind_2_derisk_1_sub_grind_count
    )
    grinds_total_stake_profit = (
      derisk_1_current_grind_stake_profit
      + grind_1_derisk_1_current_grind_stake_profit
      + grind_2_derisk_1_current_grind_stake_profit
      + grind_1_current_grind_stake_profit
      + grind_2_current_grind_stake_profit
      + grind_3_current_grind_stake_profit
      + grind_4_current_grind_stake_profit
      + grind_5_current_grind_stake_profit
      + grind_6_current_grind_stake_profit
    )
    grinds_total_amount = (
      derisk_1_total_amount
      + grind_1_derisk_1_total_amount
      + grind_2_derisk_1_total_amount
      + grind_1_total_amount
      + grind_2_total_amount
      + grind_3_total_amount
      + grind_4_total_amount
      + grind_5_total_amount
      + grind_6_total_amount
    )

    # Sell remaining if partial fill on exit
    if partial_sell:
      order = filled_exits[-1]
      sell_amount = order.safe_remaining * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        self.dp.send_msg(
          f"Exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "p"
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    if is_grind_mode and (
      (filled_entries[0].safe_filled * (trade.stake_amount / trade.amount) - (min_stake * 1.5)) > min_stake
    ):
      is_first_entry_exit_found = False
      for order in filled_orders:
        if order.ft_order_side == "sell":
          order_tag = ""
          if has_order_tags:
            if order.ft_order_tag is not None:
              sell_order_tag = order.ft_order_tag
              order_mode = sell_order_tag.split(" ", 1)
              if len(order_mode) > 0:
                order_tag = order_mode[0]
          else:
            # no order tag support, assume the first exit is for the first buy
            is_first_entry_exit_found = True
          if order_tag in ["gm0", "gmd0"]:
            is_first_entry_exit_found = True
            break
      if not is_first_entry_exit_found:
        first_entry = filled_entries[0]
        first_entry_distance_ratio = (exit_rate - first_entry.safe_price) / first_entry.safe_price
        # First entry exit
        if first_entry_distance_ratio > (
          (self.grind_mode_first_entry_profit_threshold_spot + fee_open_rate + fee_close_rate)
          if self.is_futures_mode
          else (self.grind_mode_first_entry_profit_threshold_spot + fee_open_rate + fee_close_rate)
        ):
          sell_amount = first_entry.safe_filled * exit_rate / trade.leverage
          if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
            sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
          ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
          if sell_amount > min_stake and ft_sell_amount > min_stake:
            grind_profit = (exit_rate - first_entry.safe_price) / first_entry.safe_price
            coin_amount = sell_amount / exit_rate
            self.dp.send_msg(
              f"Grinding exit (gm0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            log.info(
              f"Grinding exit (gm0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            order_tag = "gm0"
            for grind_entry_id in grind_1_buy_orders:
              order_tag += " " + str(grind_entry_id)
            if has_order_tags:
              return -ft_sell_amount, order_tag
            else:
              return -ft_sell_amount
        # First entry de-risk
        if first_entry_distance_ratio < (
          self.grind_mode_first_entry_stop_threshold_spot
          if self.is_futures_mode
          else self.grind_mode_first_entry_stop_threshold_spot
        ):
          sell_amount = first_entry.safe_filled * exit_rate / trade.leverage
          if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
            sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
          ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
          if sell_amount > min_stake and ft_sell_amount > min_stake:
            grind_profit = (exit_rate - first_entry.safe_price) / first_entry.safe_price
            coin_amount = sell_amount / exit_rate
            self.dp.send_msg(
              f"Grinding de-risk (gmd0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            log.info(
              f"Grinding de-risk (gmd0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            order_tag = "gmd0"
            for grind_entry_id in grind_1_buy_orders:
              order_tag += " " + str(grind_entry_id)
            if has_order_tags:
              return -ft_sell_amount, order_tag
            else:
              return -ft_sell_amount

    is_long_grind_buy = self.long_grind_buy(last_candle, previous_candle, slice_profit)

    # Grinding derisk 1
    # Buy
    if (
      has_order_tags
      and is_derisk_1
      and not derisk_1_reentry_found
      and (not partial_sell)
      and (grind_1_derisk_1_sub_grind_count < grind_1_derisk_1_max_sub_grinds)
    ):
      if (
        (
          (
            (grind_1_derisk_1_sub_grind_count > 0)
            and grind_1_derisk_1_distance_ratio < grind_1_derisk_1_sub_thresholds[grind_1_derisk_1_sub_grind_count]
          )
          or ((is_derisk or is_derisk_calc) and grind_1_derisk_1_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and (
          is_long_grind_buy
          or (
            (grind_1_derisk_1_sub_grind_count > 0)
            and (
              is_long_grind_buy
              or (
                (last_candle["RSI_3"] > 6.0)
                and (last_candle["AROONU_14_15m"] < 25.0)
                and (last_candle["RSI_14"] < 36.0)
                and (last_candle["close"] < (last_candle["EMA_26"] * 0.994))
              )
            )
          )
        )
      ):
        buy_amount = (
          slice_amount
          * grind_1_derisk_1_stakes[grind_1_derisk_1_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_1_derisk_1_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate
          grind_profit_stake = grind_1_derisk_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (dl1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (dl1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "dl1"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_1_derisk_1_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate
      if grind_profit > (grind_1_derisk_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_1_derisk_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (dl1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (dl1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "dl1"
          for grind_entry_id in grind_1_derisk_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (grind_1_derisk_1_sub_grind_count > 0)
      # and (
      #   ((exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate)
      #   < grind_1_derisk_1_stop_grinds
      # )
      and (grind_1_derisk_1_current_grind_stake_profit < (slice_amount * grind_1_derisk_1_stop_grinds))
      and (is_derisk or is_derisk_calc)
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_1_derisk_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_1_derisk_1_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate)
            if grind_1_derisk_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (ddl1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (ddl1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "ddl1"
        for grind_entry_id in grind_1_derisk_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding derisk 2
    # Buy
    if (
      has_order_tags
      and is_derisk_1
      and not derisk_1_reentry_found
      and (not partial_sell)
      and (grind_2_derisk_1_sub_grind_count < grind_2_derisk_1_max_sub_grinds)
    ):
      if (
        (
          (
            (grind_2_derisk_1_sub_grind_count > 0)
            and grind_2_derisk_1_distance_ratio < grind_2_derisk_1_sub_thresholds[grind_2_derisk_1_sub_grind_count]
          )
          or ((is_derisk or is_derisk_calc) and grind_2_derisk_1_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and (
          is_long_grind_buy
          or (
            (grind_2_derisk_1_sub_grind_count > 0)
            and (
              is_long_grind_buy
              or (
                (last_candle["RSI_3"] > 6.0)
                and (last_candle["AROONU_14_15m"] < 25.0)
                and (last_candle["RSI_14"] < 36.0)
                and (last_candle["close"] < (last_candle["EMA_26"] * 0.994))
              )
            )
          )
        )
      ):
        buy_amount = (
          slice_amount
          * grind_2_derisk_1_stakes[grind_2_derisk_1_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_2_derisk_1_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate
          grind_profit_stake = grind_2_derisk_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (dl2) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (dl2) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "dl2"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_2_derisk_1_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate
      if grind_profit > (grind_2_derisk_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_2_derisk_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (dl2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (dl2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "dl2"
          for grind_entry_id in grind_2_derisk_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (grind_2_derisk_1_sub_grind_count > 0)
      # and (
      #   ((exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate)
      #   < grind_2_derisk_1_stop_grinds
      # )
      and (grind_2_derisk_1_current_grind_stake_profit < (slice_amount * grind_2_derisk_1_stop_grinds))
      and (is_derisk or is_derisk_calc)
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_2_derisk_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_2_derisk_1_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate)
            if grind_2_derisk_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (ddl2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (ddl2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "ddl2"
        for grind_entry_id in grind_2_derisk_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 1
    # Buy
    if (not partial_sell) and (grind_1_sub_grind_count < grind_1_max_sub_grinds):
      if (
        (
          ((grind_1_sub_grind_count > 0) and grind_1_distance_ratio < grind_1_sub_thresholds[grind_1_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_1_sub_grind_count == 0)
          or (is_grind_mode and grind_1_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount * grind_1_stakes[grind_1_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_1_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
          grind_profit_stake = grind_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd1"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    if (
      self.is_futures_mode
      and has_order_tags
      and (not partial_sell)
      and slice_profit < (-0.65 / trade.leverage)
      and (is_derisk or is_derisk_calc or is_grind_mode)
      and (grind_1_sub_grind_count < grind_1_max_sub_grinds)
    ):
      buy_amount = (
        slice_amount * grind_1_stakes[grind_1_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
      )
      if buy_amount < (min_stake * 1.5):
        buy_amount = min_stake * 1.5
      if buy_amount > max_stake:
        return None
      grind_profit = 0.0
      grind_profit_stake = 0.0
      if grind_1_sub_grind_count > 0:
        grind_profit = (exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
        grind_profit_stake = grind_1_current_grind_stake_profit
      self.dp.send_msg(
        f"Grinding entry (gd1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      log.info(
        f"Grinding entry (gd1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      order_tag = "gd1"
      if has_order_tags:
        return buy_amount, order_tag
      else:
        return buy_amount

    # Sell
    if grind_1_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
      if grind_profit > (grind_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd1"
          for grind_entry_id in grind_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_1_sub_grind_count > 0)
        # and (((exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate) < grind_1_stop_grinds)
        and (grind_1_current_grind_stake_profit < (slice_amount * grind_1_stop_grinds))
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_1_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate)
            if grind_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd1"
        for grind_entry_id in grind_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 2
    # Buy
    if has_order_tags and (not partial_sell) and (grind_2_sub_grind_count < grind_2_max_sub_grinds):
      if (
        (
          ((grind_2_sub_grind_count > 0) and grind_2_distance_ratio < grind_2_sub_thresholds[grind_2_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_2_sub_grind_count == 0)
          or (is_grind_mode and grind_2_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount * grind_2_stakes[grind_2_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_2_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
          grind_profit_stake = grind_2_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd2) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd2) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd2"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_2_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
      if grind_profit > (grind_2_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_2_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd2"
          for grind_entry_id in grind_2_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_2_sub_grind_count > 0)
        # and (((exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate) < grind_2_stop_grinds)
        and (grind_2_current_grind_stake_profit < (slice_amount * grind_2_stop_grinds))
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_2_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_2_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate)
            if grind_2_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd2"
        for grind_entry_id in grind_2_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 3
    # Buy
    if has_order_tags and (not partial_sell) and (grind_3_sub_grind_count < grind_3_max_sub_grinds):
      if (
        (
          ((grind_3_sub_grind_count > 0) and grind_3_distance_ratio < grind_3_sub_thresholds[grind_3_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_3_sub_grind_count == 0)
          or (is_grind_mode and grind_3_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount * grind_3_stakes[grind_3_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_3_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
          grind_profit_stake = grind_3_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd3) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd3) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd3"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_3_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
      if grind_profit > (grind_3_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_3_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd3"
          for grind_entry_id in grind_3_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_3_sub_grind_count > 0)
        # and (((exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate) < grind_3_stop_grinds)
        and (grind_3_current_grind_stake_profit < (slice_amount * grind_3_stop_grinds))
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_3_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_3_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate)
            if grind_3_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd3"
        for grind_entry_id in grind_3_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 4
    # Buy
    if has_order_tags and (not partial_sell) and (grind_4_sub_grind_count < grind_4_max_sub_grinds):
      if (
        (
          ((grind_4_sub_grind_count > 0) and grind_4_distance_ratio < grind_4_sub_thresholds[grind_4_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_4_sub_grind_count == 0)
          or (is_grind_mode and grind_4_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and (
          (is_long_grind_buy)
          or (
            (last_candle["RSI_3"] > 10.0)
            and (last_candle["RSI_3_15m"] > 10.0)
            and (last_candle["RSI_14"] < 36.0)
            and (last_candle["close"] < last_candle["BBM_20_2.0"])
            and (previous_candle["close"] < previous_candle["BBM_20_2.0"])
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_4_stakes[grind_4_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_4_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
          grind_profit_stake = grind_4_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd4) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd4) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd4"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_4_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
      if grind_profit > (grind_4_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_4_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd4"
          for grind_entry_id in grind_4_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_4_sub_grind_count > 0)
        # and (((exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate) < grind_4_stop_grinds)
        and (grind_4_current_grind_stake_profit < (slice_amount * grind_4_stop_grinds))
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_4_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_4_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate)
            if grind_4_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd4"
        for grind_entry_id in grind_4_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 5
    # Buy
    if has_order_tags and (not partial_sell) and (grind_5_sub_grind_count < grind_5_max_sub_grinds):
      if (
        (
          ((grind_5_sub_grind_count > 0) and grind_5_distance_ratio < grind_5_sub_thresholds[grind_5_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_5_sub_grind_count == 0)
          or (is_grind_mode and grind_5_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount * grind_5_stakes[grind_5_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_5_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
          grind_profit_stake = grind_5_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd5) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd5) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd5"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_5_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
      if grind_profit > (grind_5_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_5_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd5"
          for grind_entry_id in grind_5_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_5_sub_grind_count > 0)
        # and (((exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate) < grind_5_stop_grinds)
        and (grind_5_current_grind_stake_profit < (slice_amount * grind_5_stop_grinds))
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_5_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_5_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate)
            if grind_5_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd5"
        for grind_entry_id in grind_5_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 6
    # Buy
    if has_order_tags and (not partial_sell) and (grind_6_sub_grind_count < grind_6_max_sub_grinds):
      if (
        (
          ((grind_6_sub_grind_count > 0) and grind_6_distance_ratio < grind_6_sub_thresholds[grind_6_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_6_sub_grind_count == 0)
          or (is_grind_mode and grind_6_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and (
          (is_long_grind_buy)
          or (
            (last_candle["RSI_3"] > 10.0)
            and (last_candle["RSI_3_15m"] > 10.0)
            and (last_candle["RSI_14"] < 36.0)
            and (last_candle["close"] < last_candle["BBM_20_2.0"])
            and (previous_candle["close"] < previous_candle["BBM_20_2.0"])
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_6_stakes[grind_6_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_6_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate
          grind_profit_stake = grind_6_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd6) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_6_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd6) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_6_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd6"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_6_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate
      if grind_profit > (grind_6_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_6_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd6) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd6) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd6"
          for grind_entry_id in grind_6_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_6_sub_grind_count > 0)
        # and (((exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate) < grind_6_stop_grinds)
        and (grind_6_current_grind_stake_profit < (slice_amount * grind_6_stop_grinds))
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 8, 16) or is_backtest)
    ):
      sell_amount = grind_6_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_6_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate)
            if grind_6_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd6) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd6) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd6"
        for grind_entry_id in grind_6_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # De-risk 1 reentry
    if (
      is_derisk_1
      and not derisk_1_reentry_found
      and derisk_1_order is not None
      and (
        ((current_rate - derisk_1_order.safe_price) / derisk_1_order.safe_price)
        < (
          self.regular_mode_derisk_1_reentry_futures
          if self.is_futures_mode
          else self.regular_mode_derisk_1_reentry_spot
        )
      )
    ):
      if (
        (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and (
          # (last_candle["protections_long_rebuy"] == True)
          # and (last_candle["protections_long_global"] == True)
          (last_candle["global_protections_long_pump"] == True)
          and (last_candle["global_protections_long_dump"] == True)
        )
        and is_long_grind_buy
      ):
        buy_amount = derisk_1_order.safe_filled * derisk_1_order.safe_price
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if derisk_1_sub_grind_count > 0:
          grind_profit = (exit_rate - derisk_1_current_open_rate) / derisk_1_current_open_rate
          grind_profit_stake = derisk_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Re-entry (d1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Re-entry (d1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "d1"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # De-risk level 1
    if (
      has_order_tags
      # and not is_derisk_1
      and derisk_1_reentry_found
      and derisk_1_reentry_order is not None
      # and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 5) or is_backtest)
      and derisk_1_distance_ratio
      < (
        (
          self.regular_mode_derisk_1_reentry_futures
          if self.is_futures_mode
          else self.regular_mode_derisk_1_reentry_spot
        )
        / (trade.leverage if self.is_futures_mode else 1.0)
      )
    ):
      sell_amount = derisk_1_reentry_order.safe_filled * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk (d1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk (d1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d1"

    # # De-risk
    # if (
    #   not is_derisk_found
    #   and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 2, 5) or is_backtest)
    #   and profit_stake
    #   < (
    #     slice_amount
    #     * (
    #       (self.regular_mode_derisk_futures if self.is_futures_mode else self.regular_mode_derisk_spot)
    #       if (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    #       else (self.regular_mode_derisk_futures_old if self.is_futures_mode else self.regular_mode_derisk_spot_old)
    #     )
    #     # / (trade.leverage if self.is_futures_mode else 1.0)
    #   )
    # ):
    #   sell_amount = trade.amount * exit_rate / trade.leverage
    #   if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
    #     sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
    #   ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
    #   if sell_amount > min_stake and ft_sell_amount > min_stake:
    #     grind_profit = 0.0
    #     self.dp.send_msg(
    #       f"De-risk [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
    #     )
    #     log.info(
    #       f"De-risk [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
    #     )
    #     return -ft_sell_amount, "d", is_derisk

    # # De-risk
    # if (num_open_grinds > 0) and (
    #   grinds_total_stake_profit
    #   < (slice_amount * (self.grinds_stop_futures if self.is_futures_mode else self.grinds_stop_spot))
    # ):
    #   sell_amount = grinds_total_amount * exit_rate / trade.leverage
    #   if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
    #     sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
    #   ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
    #   if sell_amount > min_stake and ft_sell_amount > min_stake:
    #     self.dp.send_msg(
    #       f"De-risk (dd0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
    #     )
    #     log.info(
    #       f"De-risk (dd0) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
    #     )
    #     order_tag = "dd0"
    #     for grind_entry_id in (
    #       grind_1_buy_orders
    #       + grind_2_buy_orders
    #       + grind_3_buy_orders
    #       + grind_4_buy_orders
    #       + grind_5_buy_orders
    #       + grind_6_buy_orders
    #       + grind_1_derisk_1_buy_orders
    #       + grind_2_derisk_1_buy_orders
    #     ):
    #       order_tag += " " + str(grind_entry_id)
    #     if has_order_tags:
    #       return -ft_sell_amount, order_tag
    #     else:
    #       return -ft_sell_amount

    return None

  # Long Grinding Buy
  # ---------------------------------------------------------------------------------------------
  def long_grind_buy(self, last_candle: Series, previous_candle: Series, slice_profit: float) -> float:
    if (
      (last_candle["protections_long_global"] == True)
      and (last_candle["protections_long_rebuy"] == True)
      and (last_candle["global_protections_long_pump"] == True)
      and (last_candle["global_protections_long_dump"] == True)
      # and (
      #   (last_candle["close"] > (last_candle["close_max_12"] * 0.88))
      #   and (last_candle["close"] > (last_candle["close_max_24"] * 0.82))
      #   and (last_candle["close"] > (last_candle["close_max_48"] * 0.76))
      #   and (last_candle["btc_pct_close_max_72_5m"] < 0.03)
      #   and (last_candle["btc_pct_close_max_24_5m"] < 0.03)
      # )
      and (
        (last_candle["enter_long"] == True)
        or (
          (last_candle["RSI_14"] < 36.0)
          # and (last_candle["RSI_14_15m"] < 46.0)
          and (last_candle["RSI_3"] > 6.0)
          # and (last_candle["RSI_3_15m"] > 12.0)
          # and (last_candle["RSI_3_1h"] > 12.0)
          # and (last_candle["RSI_3_4h"] > 12.0)
          # and (last_candle["WILLR_14"] > -90.0)
          # and (last_candle["WILLR_14_15m"] > -90.0)
          # and (last_candle["WILLR_14_1h"] > -90.0)
          # and (last_candle["WILLR_14_4h"] > -90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1d"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3"] > last_candle["STOCHRSId_14_14_3_3"])
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] > last_candle["STOCHRSId_14_14_3_3_1h"])
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] > last_candle["STOCHRSId_14_14_3_3_4h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] > last_candle["KSTs_9_1h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] > last_candle["KSTs_9_4h"])
          and (last_candle["close"] < (last_candle["EMA_16"] * 0.958))
        )
        or (
          (last_candle["RSI_14"] < 36.0)
          # and (previous_candle["RSI_3"] > 10.0)
          # and (last_candle["RSI_3_15m"] > 16.0)
          # and (last_candle["RSI_3_1h"] > 26.0)
          # and (last_candle["RSI_3_4h"] > 26.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1d"] < 90.0)
          # and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] > last_candle["KSTs_9_1h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] > last_candle["KSTs_9_4h"])
          and (last_candle["EMA_26"] > last_candle["EMA_12"])
          and ((last_candle["EMA_26"] - last_candle["EMA_12"]) > (last_candle["open"] * 0.030))
          and ((previous_candle["EMA_26"] - previous_candle["EMA_12"]) > (last_candle["open"] / 100.0))
          # and (last_candle["rsi_3_1h"] > 20.0)
          # and (last_candle["rsi_3_4h"] > 20.0)
          # and (last_candle["CTI_20_1h"] < 0.8)
          # and (last_candle["rsi_14_1h"] < 80.0)
        )
        or (
          (last_candle["RSI_14"] < 36.0)
          and (last_candle["RSI_3"] > 5.0)
          and (last_candle["EMA_26"] > last_candle["EMA_12"])
          and ((last_candle["EMA_26"] - last_candle["EMA_12"]) > (last_candle["open"] * 0.005))
          and ((previous_candle["EMA_26"] - previous_candle["EMA_12"]) > (last_candle["open"] / 100.0))
          and (last_candle["RSI_3_1h"] > 10.0)
        )
        or (
          (last_candle["RSI_14"] < 36.0)
          # and (last_candle["RSI_14_15m"] < 36.0)
          and (last_candle["RSI_3"] > 16.0)
          # and (last_candle["AROOND_14"] < previous_candle["AROOND_14"])
          and (last_candle["AROONU_14_15m"] < 25.0)
          and (last_candle["close"] < (last_candle["EMA_12"] * 0.984))
          # and (last_candle["RSI_3_1h"] > 10.0)
          # and (last_candle["RSI_3_4h"] > 10.0)
        )
        or (
          (last_candle["RSI_14"] < 36.0)
          # and (last_candle["WILLR_14"] > -90.0)
          # and (last_candle["WILLR_14_15m"] > -90.0)
          # and (last_candle["WILLR_14_1h"] > -90.0)
          # and (last_candle["WILLR_14_4h"] > -90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1d"] < 90.0)
          #  and (last_candle["RSI_14_15m"] < 46.0)
          # and (last_candle["RSI_3"] > 20.0)
          # and (last_candle["RSI_3_15m"] > 26.0)
          # and (last_candle["RSI_3_1h"] > 26.0)
          # and (last_candle["RSI_3_4h"] > 26.0)
          and (last_candle["AROONU_14_1h"] > last_candle["AROOND_14_1h"])
          and (last_candle["AROONU_14_4h"] > last_candle["AROOND_14_4h"])
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] > last_candle["STOCHRSId_14_14_3_3_1h"])
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] > last_candle["STOCHRSId_14_14_3_3_4h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] > last_candle["KSTs_9_1h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] > last_candle["KSTs_9_4h"])
          # and (last_candle["EMA_12_1h"] > last_candle["EMA_26_1h"])
          # and (last_candle["EMA_12_4h"] > last_candle["EMA_26_4h"])
          and (last_candle["close"] < (last_candle["EMA_26"] * 0.978))
          and (last_candle["close"] < (last_candle["BBL_20_2.0"] * 0.999))
        )
        or (
          (last_candle["RSI_14"] < 36.0)
          # and (last_candle["WILLR_14"] > -90.0)
          # and (last_candle["WILLR_14_15m"] > -90.0)
          # and (last_candle["WILLR_14_1h"] > -90.0)
          # and (last_candle["WILLR_14_4h"] > -90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] < 90.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1d"] < 90.0)
          #  and (last_candle["RSI_14_15m"] < 46.0)
          # and (last_candle["RSI_3"] > 20.0)
          # and (last_candle["RSI_3_15m"] > 26.0)
          # and (last_candle["RSI_3_1h"] > 26.0)
          # and (last_candle["RSI_3_4h"] > 26.0)
          # and (last_candle["AROONU_14_15m"] < 25.0)
          # and (last_candle["STOCHRSIk_14_14_3_3_1h"] > last_candle["STOCHRSId_14_14_3_3_1h"])
          # and (last_candle["STOCHRSIk_14_14_3_3_4h"] > last_candle["STOCHRSId_14_14_3_3_4h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_1h"] > last_candle["KSTs_9_1h"])
          # and (last_candle["KST_10_15_20_30_10_10_10_15_4h"] > last_candle["KSTs_9_4h"])
          # and (last_candle["EMA_12_1h"] > last_candle["EMA_26_1h"])
          # and (last_candle["EMA_12_4h"] > last_candle["EMA_26_4h"])
          # and (last_candle["close"] < (last_candle["EMA_100"] * 0.988))
          # and (last_candle["close"] < (last_candle["BBL_20_2.0"] * 0.998))
          and (last_candle["AROONU_14"] > last_candle["AROOND_14"])
          and (previous_candle["AROONU_14"] < previous_candle["AROOND_14"])
        )
        or (
          (last_candle["RSI_14"] < 36.0)
          # and (last_candle["RSI_3"] > 5.0)
          # and (last_candle["RSI_3_1h"] > 10.0)
          # and (last_candle["RSI_3_4h"] > 10.0)
          # and (last_candle["KST_10_15_20_30_10_10_10_15"] < -0.0)
          # and (last_candle["KSTs_9"] < -0.0)
          and (last_candle["KST_10_15_20_30_10_10_10_15"] > last_candle["KSTs_9"])
          and (previous_candle["KST_10_15_20_30_10_10_10_15"] < previous_candle["KSTs_9"])
        )
      )
    ):
      return True

    return False

  # Long Grinding Adjust Trade Position No De-Risk
  # ---------------------------------------------------------------------------------------------
  def long_adjust_trade_position_no_derisk(
    self,
    trade: Trade,
    enter_tags,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    last_candle: Series,
    previous_candle: Series,
    filled_orders: "Orders",
    filled_entries: "Orders",
    filled_exits: "Orders",
    exit_rate: float,
    slice_amount: float,
    slice_profit_entry: float,
    slice_profit: float,
    profit_ratio: float,
    profit_stake: float,
    profit_init_ratio: float,
    current_stake_amount: float,
    has_order_tags: bool,
    **kwargs,
  ) -> tuple[Optional[float], str, bool]:
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]

    max_rebuy_sub_grinds = 0
    regular_mode_rebuy_stakes = (
      self.regular_mode_rebuy_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_rebuy_stakes_spot.copy()
    )
    regular_mode_rebuy_sub_thresholds = (
      self.regular_mode_rebuy_thresholds_futures if self.is_futures_mode else self.regular_mode_rebuy_thresholds_spot
    )
    if (slice_amount * regular_mode_rebuy_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_rebuy_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_rebuy_stakes):
        regular_mode_rebuy_stakes[i] *= multi
    max_rebuy_sub_grinds = len(regular_mode_rebuy_stakes)

    max_grind_1_sub_grinds = 0
    regular_mode_grind_1_stakes = (
      self.regular_mode_grind_1_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_1_stakes_spot.copy()
    )
    regular_mode_grind_1_sub_thresholds = (
      self.regular_mode_grind_1_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_1_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_1_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_1_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_1_stakes):
        regular_mode_grind_1_stakes[i] *= multi
    max_grind_1_sub_grinds = len(regular_mode_grind_1_stakes)
    regular_mode_grind_1_stop_grinds = (
      self.regular_mode_grind_1_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_1_stop_grinds_spot
    )
    regular_mode_grind_1_profit_threshold = (
      self.regular_mode_grind_1_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_1_profit_threshold_spot
    )

    max_grind_2_sub_grinds = 0
    regular_mode_grind_2_stakes = (
      self.regular_mode_grind_2_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_2_stakes_spot.copy()
    )
    regular_mode_grind_2_sub_thresholds = (
      self.regular_mode_grind_2_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_2_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_2_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_2_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_2_stakes):
        regular_mode_grind_2_stakes[i] *= multi
    max_grind_2_sub_grinds = len(regular_mode_grind_2_stakes)
    regular_mode_grind_2_stop_grinds = (
      self.regular_mode_grind_2_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_2_stop_grinds_spot
    )
    regular_mode_grind_2_profit_threshold = (
      self.regular_mode_grind_2_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_2_profit_threshold_spot
    )

    max_grind_3_sub_grinds = 0
    regular_mode_grind_3_stakes = (
      self.regular_mode_grind_3_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_3_stakes_spot.copy()
    )
    regular_mode_grind_3_sub_thresholds = (
      self.regular_mode_grind_3_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_3_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_3_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_3_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_3_stakes):
        regular_mode_grind_3_stakes[i] *= multi
    max_grind_3_sub_grinds = len(regular_mode_grind_3_stakes)
    regular_mode_grind_3_stop_grinds = (
      self.regular_mode_grind_3_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_3_stop_grinds_spot
    )
    regular_mode_grind_3_profit_threshold = (
      self.regular_mode_grind_3_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_3_profit_threshold_spot
    )

    max_grind_4_sub_grinds = 0
    regular_mode_grind_4_stakes = (
      self.regular_mode_grind_4_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_4_stakes_spot.copy()
    )
    regular_mode_grind_4_sub_thresholds = (
      self.regular_mode_grind_4_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_4_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_4_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_4_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_4_stakes):
        regular_mode_grind_4_stakes[i] *= multi
    max_grind_4_sub_grinds = len(regular_mode_grind_4_stakes)
    regular_mode_grind_4_stop_grinds = (
      self.regular_mode_grind_4_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_4_stop_grinds_spot
    )
    regular_mode_grind_4_profit_threshold = (
      self.regular_mode_grind_4_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_4_profit_threshold_spot
    )

    max_grind_5_sub_grinds = 0
    regular_mode_grind_5_stakes = (
      self.regular_mode_grind_5_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_5_stakes_spot.copy()
    )
    regular_mode_grind_5_sub_thresholds = (
      self.regular_mode_grind_5_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_5_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_5_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_5_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_5_stakes):
        regular_mode_grind_5_stakes[i] *= multi
    max_grind_5_sub_grinds = len(regular_mode_grind_5_stakes)
    regular_mode_grind_5_stop_grinds = (
      self.regular_mode_grind_5_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_5_stop_grinds_spot
    )
    regular_mode_grind_5_profit_threshold = (
      self.regular_mode_grind_5_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_5_profit_threshold_spot
    )

    max_grind_6_sub_grinds = 0
    regular_mode_grind_6_stakes = (
      self.regular_mode_grind_6_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_6_stakes_spot.copy()
    )
    regular_mode_grind_6_sub_thresholds = (
      self.regular_mode_grind_6_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_6_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_6_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_6_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_6_stakes):
        regular_mode_grind_6_stakes[i] *= multi
    max_grind_6_sub_grinds = len(regular_mode_grind_6_stakes)
    regular_mode_grind_6_stop_grinds = (
      self.regular_mode_grind_6_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_6_stop_grinds_spot
    )
    regular_mode_grind_6_profit_threshold = (
      self.regular_mode_grind_6_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_6_profit_threshold_spot
    )

    partial_sell = False
    is_derisk = False
    is_derisk_1 = False
    rebuy_sub_grind_count = 0
    rebuy_total_amount = 0.0
    rebuy_total_cost = 0.0
    rebuy_current_open_rate = 0.0
    rebuy_current_grind_stake = 0.0
    rebuy_current_grind_stake_profit = 0.0
    rebuy_is_sell_found = False
    rebuy_found = False
    rebuy_buy_orders = []
    rebuy_distance_ratio = 0.0
    grind_1_sub_grind_count = 0
    grind_1_total_amount = 0.0
    grind_1_total_cost = 0.0
    grind_1_current_open_rate = 0.0
    grind_1_current_grind_stake = 0.0
    grind_1_current_grind_stake_profit = 0.0
    grind_1_is_sell_found = False
    grind_1_found = False
    grind_1_buy_orders = []
    grind_1_distance_ratio = 0.0
    grind_2_sub_grind_count = 0
    grind_2_total_amount = 0.0
    grind_2_total_cost = 0.0
    grind_2_current_open_rate = 0.0
    grind_2_current_grind_stake = 0.0
    grind_2_current_grind_stake_profit = 0.0
    grind_2_is_sell_found = False
    grind_2_found = False
    grind_2_buy_orders = []
    grind_2_distance_ratio = 0.0
    grind_3_sub_grind_count = 0
    grind_3_total_amount = 0.0
    grind_3_total_cost = 0.0
    grind_3_current_open_rate = 0.0
    grind_3_current_grind_stake = 0.0
    grind_3_current_grind_stake_profit = 0.0
    grind_3_is_sell_found = False
    grind_3_found = False
    grind_3_buy_orders = []
    grind_3_distance_ratio = 0.0
    grind_4_sub_grind_count = 0
    grind_4_total_amount = 0.0
    grind_4_total_cost = 0.0
    grind_4_current_open_rate = 0.0
    grind_4_current_grind_stake = 0.0
    grind_4_current_grind_stake_profit = 0.0
    grind_4_is_sell_found = False
    grind_4_found = False
    grind_4_buy_orders = []
    grind_4_distance_ratio = 0.0
    grind_5_sub_grind_count = 0
    grind_5_total_amount = 0.0
    grind_5_total_cost = 0.0
    grind_5_current_open_rate = 0.0
    grind_5_current_grind_stake = 0.0
    grind_5_current_grind_stake_profit = 0.0
    grind_5_is_sell_found = False
    grind_5_found = False
    grind_5_buy_orders = []
    grind_5_distance_ratio = 0.0
    grind_6_sub_grind_count = 0
    grind_6_total_amount = 0.0
    grind_6_total_cost = 0.0
    grind_6_current_open_rate = 0.0
    grind_6_current_grind_stake = 0.0
    grind_6_current_grind_stake_profit = 0.0
    grind_6_is_sell_found = False
    grind_6_found = False
    grind_6_buy_orders = []
    grind_6_distance_ratio = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        if not grind_1_is_sell_found and order_tag == "g1":
          grind_1_sub_grind_count += 1
          grind_1_total_amount += order.safe_filled
          grind_1_total_cost += order.safe_filled * order.safe_price
          grind_1_buy_orders.append(order.id)
          if not grind_1_found:
            grind_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_1_found = True
        elif not grind_2_is_sell_found and order_tag == "g2":
          grind_2_sub_grind_count += 1
          grind_2_total_amount += order.safe_filled
          grind_2_total_cost += order.safe_filled * order.safe_price
          grind_2_buy_orders.append(order.id)
          if not grind_2_found:
            grind_2_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_2_found = True
        elif not grind_3_is_sell_found and order_tag == "g3":
          grind_3_sub_grind_count += 1
          grind_3_total_amount += order.safe_filled
          grind_3_total_cost += order.safe_filled * order.safe_price
          grind_3_buy_orders.append(order.id)
          if not grind_3_found:
            grind_3_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_3_found = True
        elif not grind_4_is_sell_found and order_tag == "g4":
          grind_4_sub_grind_count += 1
          grind_4_total_amount += order.safe_filled
          grind_4_total_cost += order.safe_filled * order.safe_price
          grind_4_buy_orders.append(order.id)
          if not grind_4_found:
            grind_4_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_4_found = True
        elif not grind_5_is_sell_found and order_tag == "g5":
          grind_5_sub_grind_count += 1
          grind_5_total_amount += order.safe_filled
          grind_5_total_cost += order.safe_filled * order.safe_price
          grind_5_buy_orders.append(order.id)
          if not grind_5_found:
            grind_5_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_5_found = True
        elif not grind_6_is_sell_found and order_tag == "g6":
          grind_6_sub_grind_count += 1
          grind_6_total_amount += order.safe_filled
          grind_6_total_cost += order.safe_filled * order.safe_price
          grind_6_buy_orders.append(order.id)
          if not grind_6_found:
            grind_6_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_6_found = True
        elif not rebuy_is_sell_found and order_tag not in [
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "sg1",
          "sg2",
          "sg3",
          "sg4",
          "sg5",
          "sg6",
          "dl1",
          "dl2",
          "gd1",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "gm0",
          "gmd0",
        ]:
          rebuy_sub_grind_count += 1
          rebuy_total_amount += order.safe_filled
          rebuy_total_cost += order.safe_filled * order.safe_price
          rebuy_buy_orders.append(order.id)
          if not rebuy_found:
            rebuy_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            rebuy_found = True
      elif order.ft_order_side == "sell":
        if (
          order is filled_exits[-1]
          and (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake
        ):
          partial_sell = True
          break
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            sell_order_tag = order.ft_order_tag
            order_mode = sell_order_tag.split(" ", 1)
            if len(order_mode) > 0:
              order_tag = order_mode[0]
        if order_tag in ["g1", "sg1"]:
          grind_1_is_sell_found = True
        elif order_tag in ["g2", "sg2"]:
          grind_2_is_sell_found = True
        elif order_tag in ["g3", "sg3"]:
          grind_3_is_sell_found = True
        elif order_tag in ["g4", "sg4"]:
          grind_4_is_sell_found = True
        elif order_tag in ["g5", "sg5"]:
          grind_5_is_sell_found = True
        elif order_tag in ["g6", "sg6"]:
          grind_6_is_sell_found = True
        elif order_tag in ["d", "d1", "dd0", "ddl1", "ddl2", "dd1", "dd2", "dd3", "dd4", "dd5", "dd6"]:
          is_derisk = True
          if order_tag in ["d1"]:
            is_derisk_1 = True
          grind_1_is_sell_found = True
          grind_2_is_sell_found = True
          grind_3_is_sell_found = True
          grind_4_is_sell_found = True
          grind_5_is_sell_found = True
          grind_6_is_sell_found = True
          rebuy_is_sell_found = True
        elif order_tag not in [
          "p",
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "sg1",
          "sg2",
          "sg3",
          "sg4",
          "sg5",
          "sg6",
          "dl1",
          "dl2",
          "gd1",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "gm0",
          "gmd0",
        ]:
          rebuy_is_sell_found = True
        if not is_derisk:
          start_amount = filled_orders[0].safe_filled
          current_amount = 0.0
          for order2 in filled_orders:
            if order2.ft_order_side == "buy":
              current_amount += order2.safe_filled
            elif order2.ft_order_side == "sell":
              current_amount -= order2.safe_filled
            if order2 is order:
              if current_amount < (start_amount * 0.95):
                is_derisk = True
        # found sells for all modes
        if (
          rebuy_is_sell_found
          and grind_1_is_sell_found
          and grind_2_is_sell_found
          and grind_3_is_sell_found
          and grind_4_is_sell_found
          and grind_5_is_sell_found
          and grind_6_is_sell_found
        ):
          break

    # The trade already de-risked
    if is_derisk:
      return None, "", is_derisk
    if not has_order_tags and len(filled_exits) > 0:
      return None, "", is_derisk

    if rebuy_sub_grind_count > 0:
      rebuy_current_open_rate = rebuy_total_cost / rebuy_total_amount
      rebuy_current_grind_stake = rebuy_total_amount * exit_rate * (1 - trade.fee_close)
      rebuy_current_grind_stake_profit = rebuy_current_grind_stake - rebuy_total_cost
    if grind_1_sub_grind_count > 0:
      grind_1_current_open_rate = grind_1_total_cost / grind_1_total_amount
      grind_1_current_grind_stake = grind_1_total_amount * exit_rate * (1 - trade.fee_close)
      grind_1_current_grind_stake_profit = grind_1_current_grind_stake - grind_1_total_cost
    if grind_2_sub_grind_count > 0:
      grind_2_current_open_rate = grind_2_total_cost / grind_2_total_amount
      grind_2_current_grind_stake = grind_2_total_amount * exit_rate * (1 - trade.fee_close)
      grind_2_current_grind_stake_profit = grind_2_current_grind_stake - grind_2_total_cost
    if grind_3_sub_grind_count > 0:
      grind_3_current_open_rate = grind_3_total_cost / grind_3_total_amount
      grind_3_current_grind_stake = grind_3_total_amount * exit_rate * (1 - trade.fee_close)
      grind_3_current_grind_stake_profit = grind_3_current_grind_stake - grind_3_total_cost
    if grind_4_sub_grind_count > 0:
      grind_4_current_open_rate = grind_4_total_cost / grind_4_total_amount
      grind_4_current_grind_stake = grind_4_total_amount * exit_rate * (1 - trade.fee_close)
      grind_4_current_grind_stake_profit = grind_4_current_grind_stake - grind_4_total_cost
    if grind_5_sub_grind_count > 0:
      grind_5_current_open_rate = grind_5_total_cost / grind_5_total_amount
      grind_5_current_grind_stake = grind_5_total_amount * exit_rate * (1 - trade.fee_close)
      grind_5_current_grind_stake_profit = grind_5_current_grind_stake - grind_5_total_cost
    if grind_6_sub_grind_count > 0:
      grind_6_current_open_rate = grind_6_total_cost / grind_6_total_amount
      grind_6_current_grind_stake = grind_6_total_amount * exit_rate * (1 - trade.fee_close)
      grind_6_current_grind_stake_profit = grind_6_current_grind_stake - grind_6_total_cost

    num_open_grinds = (
      grind_1_sub_grind_count
      + grind_2_sub_grind_count
      + grind_3_sub_grind_count
      + grind_4_sub_grind_count
      + grind_5_sub_grind_count
      + grind_6_sub_grind_count
    )

    fee_open_rate = trade.fee_open if self.custom_fee_open_rate is None else self.custom_fee_open_rate
    fee_close_rate = trade.fee_close if self.custom_fee_close_rate is None else self.custom_fee_close_rate

    # Sell remaining if partial fill on exit
    if partial_sell:
      order = filled_exits[-1]
      sell_amount = order.safe_remaining * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        self.dp.send_msg(
          f"Exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "p"
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        return -ft_sell_amount, order_tag, is_derisk

    is_long_grind_buy = self.long_grind_buy(last_candle, previous_candle, slice_profit)

    # Rebuy
    if (not partial_sell) and (not rebuy_is_sell_found) and (rebuy_sub_grind_count < max_rebuy_sub_grinds):
      if (
        (0 <= rebuy_sub_grind_count < max_rebuy_sub_grinds)
        and (slice_profit_entry < regular_mode_rebuy_sub_thresholds[rebuy_sub_grind_count])
        and (
          (rebuy_distance_ratio if (rebuy_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_rebuy_sub_thresholds[rebuy_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=12) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.06))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount
          * regular_mode_rebuy_stakes[rebuy_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount > max_stake:
          buy_amount = max_stake
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        self.dp.send_msg(
          f"Rebuy (r) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"Rebuy (r) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "r"
        return buy_amount, order_tag, is_derisk

    # Grinding g1
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_1_sub_grind_count < max_grind_1_sub_grinds):
      if (
        (
          (grind_1_distance_ratio if (grind_1_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_1_sub_thresholds[grind_1_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_1_stakes[grind_1_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_1_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
          grind_profit_stake = grind_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g1"
        return buy_amount, order_tag, is_derisk

    if (
      self.is_futures_mode
      and has_order_tags
      and (not partial_sell)
      and slice_profit < (-0.65 / trade.leverage)
      and (grind_1_sub_grind_count < max_grind_1_sub_grinds)
    ):
      buy_amount = (
        slice_amount
        * regular_mode_grind_1_stakes[grind_1_sub_grind_count]
        / (trade.leverage if self.is_futures_mode else 1.0)
      )
      if buy_amount < (min_stake * 1.5):
        buy_amount = min_stake * 1.5
      if buy_amount > max_stake:
        return None, "", is_derisk
      grind_profit = 0.0
      grind_profit_stake = 0.0
      if grind_1_sub_grind_count > 0:
        grind_profit = (exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
        grind_profit_stake = grind_1_current_grind_stake_profit
      self.dp.send_msg(
        f"Grinding entry (g1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      log.info(
        f"Grinding entry (g1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      order_tag = "g1"
      return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_1_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
      if grind_profit > (regular_mode_grind_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g1"
          for grind_entry_id in grind_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Grind stop
    if (
      (
        (grind_1_sub_grind_count > 0)
        and self.regular_mode_use_grind_stops
        and (((exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate) < regular_mode_grind_1_stop_grinds)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    ):
      sell_amount = grind_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_1_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate)
            if grind_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (sg1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (sg1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "sg1"
        for grind_entry_id in grind_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        return -ft_sell_amount, order_tag, is_derisk

    # Grinding g2
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_2_sub_grind_count < max_grind_2_sub_grinds):
      if (
        (
          (grind_2_distance_ratio if (grind_2_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_2_sub_thresholds[grind_2_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_2_stakes[grind_2_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_2_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
          grind_profit_stake = grind_2_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g2) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g2) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g2"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_2_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
      if grind_profit > (regular_mode_grind_2_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_2_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g2"
          for grind_entry_id in grind_2_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Grind stop
    if (
      (
        (grind_2_sub_grind_count > 0)
        and self.regular_mode_use_grind_stops
        and (((exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate) < regular_mode_grind_2_stop_grinds)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    ):
      sell_amount = grind_2_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_2_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate)
            if grind_2_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (sg2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (sg2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "sg2"
        for grind_entry_id in grind_2_buy_orders:
          order_tag += " " + str(grind_entry_id)
        return -ft_sell_amount, order_tag, is_derisk

    # Grinding g3
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_3_sub_grind_count < max_grind_3_sub_grinds):
      if (
        (
          (grind_3_distance_ratio if (grind_3_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_3_sub_thresholds[grind_3_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_3_stakes[grind_3_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_3_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
          grind_profit_stake = grind_3_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g3) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g3) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g3"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_3_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
      if grind_profit > (regular_mode_grind_3_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_3_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g3"
          for grind_entry_id in grind_3_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Grind stop
    if (
      (
        (grind_3_sub_grind_count > 0)
        and self.regular_mode_use_grind_stops
        and (((exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate) < regular_mode_grind_3_stop_grinds)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    ):
      sell_amount = grind_3_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_3_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate)
            if grind_3_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (sg3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (sg3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "sg3"
        for grind_entry_id in grind_3_buy_orders:
          order_tag += " " + str(grind_entry_id)
        return -ft_sell_amount, order_tag, is_derisk

    # Grinding g4
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_4_sub_grind_count < max_grind_4_sub_grinds):
      if (
        (
          (grind_4_distance_ratio if (grind_4_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_4_sub_thresholds[grind_4_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_4_stakes[grind_4_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_4_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
          grind_profit_stake = grind_4_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g4) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g4) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g4"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_4_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
      if grind_profit > (regular_mode_grind_4_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_4_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g4"
          for grind_entry_id in grind_4_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Grind stop
    if (
      (
        (grind_4_sub_grind_count > 0)
        and self.regular_mode_use_grind_stops
        and (((exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate) < regular_mode_grind_4_stop_grinds)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    ):
      sell_amount = grind_4_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_4_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate)
            if grind_4_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (sg4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (sg4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "sg4"
        for grind_entry_id in grind_4_buy_orders:
          order_tag += " " + str(grind_entry_id)
        return -ft_sell_amount, order_tag, is_derisk

    # Grinding g5
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_5_sub_grind_count < max_grind_5_sub_grinds):
      if (
        (
          (grind_5_distance_ratio if (grind_5_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_5_sub_thresholds[grind_5_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and is_long_grind_buy
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_5_stakes[grind_5_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_5_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
          grind_profit_stake = grind_5_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g5) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g5) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g5"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_5_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
      if grind_profit > (regular_mode_grind_5_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_5_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g5"
          for grind_entry_id in grind_5_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Grind stop
    if (
      (
        (grind_5_sub_grind_count > 0)
        and self.regular_mode_use_grind_stops
        and (((exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate) < regular_mode_grind_5_stop_grinds)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    ):
      sell_amount = grind_5_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_5_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate)
            if grind_5_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (sg5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (sg5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "sg5"
        for grind_entry_id in grind_5_buy_orders:
          order_tag += " " + str(grind_entry_id)
        return -ft_sell_amount, order_tag, is_derisk

    # Grinding g6
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_6_sub_grind_count < max_grind_6_sub_grinds):
      if (
        (
          (grind_6_distance_ratio if (grind_6_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_6_sub_thresholds[grind_6_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit < -0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit < -0.06)
        )
        # and ((num_open_grinds == 0) or (slice_profit < -0.03))
        and (
          (is_long_grind_buy)
          or (
            (last_candle["RSI_3"] > 10.0)
            and (last_candle["RSI_3_15m"] > 10.0)
            and (last_candle["RSI_14"] < 36.0)
            and (last_candle["close"] < last_candle["BBM_20_2.0"])
            and (previous_candle["close"] < previous_candle["BBM_20_2.0"])
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_6_stakes[grind_6_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_6_sub_grind_count > 0:
          grind_profit = (exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate
          grind_profit_stake = grind_6_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g6) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_6_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g6) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_6_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g6"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_6_sub_grind_count > 0:
      grind_profit = (exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate
      if grind_profit > (regular_mode_grind_6_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_6_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g6) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g6) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g6"
          for grind_entry_id in grind_6_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Grind stop
    if (
      (
        (grind_6_sub_grind_count > 0)
        and self.regular_mode_use_grind_stops
        and (((exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate) < regular_mode_grind_6_stop_grinds)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
    ):
      sell_amount = grind_6_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_6_current_open_rate > 0.0:
          grind_profit = (
            ((exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate)
            if grind_6_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (sg6) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (sg6) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "sg6"
        for grind_entry_id in grind_6_buy_orders:
          order_tag += " " + str(grind_entry_id)
        return -ft_sell_amount, order_tag, is_derisk

    # De-risk
    if profit_stake < (
      slice_amount
      * (
        (self.regular_mode_derisk_futures if self.is_futures_mode else self.regular_mode_derisk_spot)
        if (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 3, 19) or is_backtest)
        else (self.regular_mode_derisk_futures_old if self.is_futures_mode else self.regular_mode_derisk_spot_old)
      )
      # / (trade.leverage if self.is_futures_mode else 1.0)
    ):
      sell_amount = trade.amount * exit_rate / trade.leverage - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d", is_derisk

    # De-risk level 1
    if (
      has_order_tags
      and not is_derisk_1
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 5) or is_backtest)
      and profit_stake
      < (
        slice_amount
        * (
          (self.regular_mode_derisk_1_futures if self.is_futures_mode else self.regular_mode_derisk_1_spot)
          if (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 16) or is_backtest)
          else (
            self.regular_mode_derisk_1_futures_old if self.is_futures_mode else self.regular_mode_derisk_1_spot_old
          )
        )
      )
    ):
      sell_amount = trade.amount * exit_rate / trade.leverage - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk (d1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk (d1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d1", is_derisk

    return None, "", is_derisk

  # Long Rebuy Adjust Trade Position
  # ---------------------------------------------------------------------------------------------
  def long_rebuy_adjust_trade_position(
    self,
    trade: Trade,
    enter_tags,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ) -> Optional[float]:
    # min/max stakes include leverage. The return amounts is before leverage.
    min_stake /= trade.leverage
    max_stake /= trade.leverage
    df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
    if len(df) < 2:
      return None
    last_candle = df.iloc[-1].squeeze()
    previous_candle = df.iloc[-2].squeeze()

    filled_orders = trade.select_filled_orders()
    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)
    count_of_entries = trade.nr_of_successful_entries
    count_of_exits = trade.nr_of_successful_exits

    if count_of_entries == 0:
      return None

    has_order_tags = False
    if hasattr(filled_orders[0], "ft_order_tag"):
      has_order_tags = True

    # The first exit is de-risk (providing the trade is still open)
    if count_of_exits > 0:
      return self.long_grind_adjust_trade_position(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    exit_rate = current_rate
    if self.dp.runmode.value in ("live", "dry_run"):
      ticker = self.dp.ticker(trade.pair)
      if ("bid" in ticker) and ("ask" in ticker):
        if trade.is_short:
          if self.config["exit_pricing"]["price_side"] in ["ask", "other"]:
            if ticker["ask"] is not None:
              exit_rate = ticker["ask"]
        else:
          if self.config["exit_pricing"]["price_side"] in ["bid", "other"]:
            if ticker["bid"] is not None:
              exit_rate = ticker["bid"]

    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, exit_rate
    )

    slice_amount = filled_entries[0].cost
    slice_profit = (exit_rate - filled_orders[-1].safe_price) / filled_orders[-1].safe_price
    slice_profit_entry = (exit_rate - filled_entries[-1].safe_price) / filled_entries[-1].safe_price
    slice_profit_exit = (
      ((exit_rate - filled_exits[-1].safe_price) / filled_exits[-1].safe_price) if count_of_exits > 0 else 0.0
    )

    current_stake_amount = trade.amount * current_rate

    is_rebuy = False

    rebuy_mode_stakes = self.rebuy_mode_stakes_futures if self.is_futures_mode else self.rebuy_mode_stakes_spot
    max_sub_grinds = len(rebuy_mode_stakes)
    rebuy_mode_sub_thresholds = (
      self.rebuy_mode_thresholds_futures if self.is_futures_mode else self.rebuy_mode_thresholds_spot
    )
    partial_sell = False
    sub_grind_count = 0
    total_amount = 0.0
    total_cost = 0.0
    current_open_rate = 0.0
    current_grind_stake = 0.0
    current_grind_stake_profit = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
        sub_grind_count += 1
        total_amount += order.safe_filled
        total_cost += order.safe_filled * order.safe_price
      elif order.ft_order_side == "sell":
        if (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake:
          partial_sell = True
        break
    if sub_grind_count > 0:
      current_open_rate = total_cost / total_amount
      current_grind_stake = total_amount * exit_rate * (1 - trade.fee_close)
      current_grind_stake_profit = current_grind_stake - total_cost

    if (not partial_sell) and (sub_grind_count < max_sub_grinds):
      if (
        ((0 <= sub_grind_count < max_sub_grinds) and (slice_profit_entry < rebuy_mode_sub_thresholds[sub_grind_count]))
        and (last_candle["protections_long_global"] == True)
        and (last_candle["protections_long_rebuy"] == True)
        and (last_candle["global_protections_long_pump"] == True)
        and (last_candle["global_protections_long_dump"] == True)
        # and (
        #   (last_candle["close"] > (last_candle["close_max_12"] * 0.94))
        #   and (last_candle["close"] > (last_candle["close_max_24"] * 0.92))
        #   and (last_candle["close"] > (last_candle["close_max_48"] * 0.90))
        #   and (last_candle["close"] > (last_candle["high_max_24_1h"] * 0.88))
        #   and (last_candle["close"] > (last_candle["high_max_48_1h"] * 0.86))
        #   and (last_candle["btc_pct_close_max_72_5m"] < 0.03)
        #   and (last_candle["btc_pct_close_max_24_5m"] < 0.03)
        # )
        and (
          (last_candle["RSI_3"] > 10.0)
          and (last_candle["RSI_3_15m"] > 10.0)
          and (last_candle["RSI_3_1h"] > 10.0)
          and (last_candle["RSI_3_4h"] > 10.0)
          and (last_candle["RSI_14"] < 36.0)
          and (last_candle["close"] < (last_candle["EMA_26"] * 0.988))
        )
      ):
        buy_amount = (
          slice_amount * rebuy_mode_stakes[sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount > max_stake:
          buy_amount = max_stake
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        self.dp.send_msg(
          f"Rebuy (r) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"Rebuy (r) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        if has_order_tags:
          return buy_amount, "r"
        else:
          return buy_amount

      if profit_stake < (
        slice_amount * (self.rebuy_mode_derisk_futures if self.is_futures_mode else self.rebuy_mode_derisk_spot)
        # / (trade.leverage if self.is_futures_mode else 1.0)
      ):
        sell_amount = trade.amount * exit_rate / trade.leverage - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          grind_profit = 0.0
          self.dp.send_msg(
            f"Rebuy de-risk (d1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
          )
          log.info(
            f"Rebuy de-risk (d1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
          )
          if has_order_tags:
            return -ft_sell_amount, "d1"
          else:
            return -ft_sell_amount

    return None

  ###############################################################################################
  # LONG EXIT FUNCTIONS ENDS HERE
  ###############################################################################################

  #   ______   __    __   ______   _______  ________         ______   ______  _______   ________
  #  /      \ |  \  |  \ /      \ |       \|        \       /      \ |      \|       \ |        \
  # |  $$$$$$\| $$  | $$|  $$$$$$\| $$$$$$$\\$$$$$$$$      |  $$$$$$\ \$$$$$$| $$$$$$$\| $$$$$$$$
  # | $$___\$$| $$__| $$| $$  | $$| $$__| $$  | $$         | $$___\$$  | $$  | $$  | $$| $$__
  #  \$$    \ | $$    $$| $$  | $$| $$    $$  | $$          \$$    \   | $$  | $$  | $$| $$  \
  #  _\$$$$$$\| $$$$$$$$| $$  | $$| $$$$$$$\  | $$          _\$$$$$$\  | $$  | $$  | $$| $$$$$
  # |  \__| $$| $$  | $$| $$__/ $$| $$  | $$  | $$         |  \__| $$ _| $$_ | $$__/ $$| $$_____
  #  \$$    $$| $$  | $$ \$$    $$| $$  | $$  | $$          \$$    $$|   $$ \| $$    $$| $$     \
  #   \$$$$$$  \$$   \$$  \$$$$$$  \$$   \$$   \$$           \$$$$$$  \$$$$$$ \$$$$$$$  \$$$$$$$$
  #

  # Short Side Functions for handling short orders
  # ---------------------------------------------------------------------------------------------

  #   ______  __    __  ______  _______ ________        ________ __    __ ______ ________
  #  /      \|  \  |  \/      \|       |        \      |        |  \  |  |      |        \
  # |  $$$$$$| $$  | $|  $$$$$$| $$$$$$$\$$$$$$$$      | $$$$$$$| $$  | $$\$$$$$$\$$$$$$$$
  # | $$___\$| $$__| $| $$  | $| $$__| $$ | $$         | $$__    \$$\/  $$ | $$    | $$
  #  \$$    \| $$    $| $$  | $| $$    $$ | $$         | $$  \    >$$  $$  | $$    | $$
  #  _\$$$$$$| $$$$$$$| $$  | $| $$$$$$$\ | $$         | $$$$$   /  $$$$\  | $$    | $$
  # |  \__| $| $$  | $| $$__/ $| $$  | $$ | $$         | $$_____|  $$ \$$\_| $$_   | $$
  #  \$$    $| $$  | $$\$$    $| $$  | $$ | $$         | $$     | $$  | $|   $$ \  | $$
  #   \$$$$$$ \$$   \$$ \$$$$$$ \$$   \$$  \$$          \$$$$$$$$\$$   \$$\$$$$$$   \$$
  #

  ###############################################################################################
  # SHORT EXIT FUNCTIONS STARTS HERE
  ###############################################################################################

  # Short Exit Normal
  # ---------------------------------------------------------------------------------------------
  def short_exit_normal(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.short_exit_signals(
      self.short_normal_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.short_exit_main(
        self.short_normal_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.short_exit_williams_r(
        self.short_normal_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.short_exit_dec(
        self.short_normal_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.short_exit_stoploss(
        self.short_normal_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_normal_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_normal_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_normal_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.short_normal_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_normal_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_normal_mode_name}_stoploss_doom",
        f"exit_{self.short_normal_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_normal_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= self.profit_max_thresholds[0]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.short_normal_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.short_normal_mode_name}_max",
      f"exit_{self.short_normal_mode_name}_stoploss_doom",
      f"exit_{self.short_normal_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Short Exit Pump
  # ---------------------------------------------------------------------------------------------
  def short_exit_pump(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.short_exit_signals(
      self.short_pump_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.short_exit_main(
        self.short_pump_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.short_exit_williams_r(
        self.short_pump_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.short_exit_dec(
        self.short_pump_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.short_exit_stoploss(
        self.short_pump_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_pump_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_pump_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_pump_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.short_pump_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_pump_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_pump_mode_name}_stoploss_doom",
        f"exit_{self.short_pump_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_pump_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_pump_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= self.profit_max_thresholds[2]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.short_pump_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.short_pump_mode_name}_max",
      f"exit_{self.short_pump_mode_name}_stoploss_doom",
      f"exit_{self.short_pump_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Short Exit Quick
  # ---------------------------------------------------------------------------------------------
  def short_exit_quick(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.short_exit_signals(
      self.short_quick_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.short_exit_main(
        self.short_quick_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.short_exit_williams_r(
        self.short_quick_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.short_exit_dec(
        self.short_quick_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.short_exit_stoploss(
        self.short_quick_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Extra sell logic
    if not sell:
      if (0.09 >= profit_init_ratio > 0.02) and (last_candle["RSI_14"] < 22.0):
        sell, signal_name = True, f"exit_{self.short_quick_mode_name}_q_1"

      if (0.09 >= profit_init_ratio > 0.02) and (last_candle["CTI_20"] < -0.95):
        sell, signal_name = True, f"exit_{self.short_quick_mode_name}_q_2"

      if (0.09 >= profit_init_ratio > 0.02) and (last_candle["WILLR_14"] <= -0.99):
        sell, signal_name = True, f"exit_{self.short_quick_mode_name}_q_3"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_quick_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_quick_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_quick_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.short_quick_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_quick_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_quick_mode_name}_stoploss_doom",
        f"exit_{self.short_quick_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_quick_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_quick_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= self.profit_max_thresholds[4]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.short_quick_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.short_quick_mode_name}_max",
      f"exit_{self.short_quick_mode_name}_stoploss_doom",
      f"exit_{self.short_quick_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Short Exit Rebuy
  # ---------------------------------------------------------------------------------------------
  def short_exit_rebuy(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.short_exit_signals(
      self.short_rebuy_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.short_exit_main(
        self.short_rebuy_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.short_exit_williams_r(
        self.short_rebuy_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.short_exit_dec(
        self.short_rebuy_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      if profit_stake < -(
        filled_entries[0].cost
        * (self.stop_threshold_futures_rebuy if self.is_futures_mode else self.stop_threshold_spot_rebuy)
        / (trade.leverage if self.is_futures_mode else 1.0)
      ):
        sell, signal_name = True, f"exit_{self.short_rebuy_mode_name}_stoploss_doom"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_rebuy_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_rebuy_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_rebuy_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.short_rebuy_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_rebuy_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_rebuy_mode_name}_stoploss_doom",
        f"exit_{self.short_rebuy_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_rebuy_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_rebuy_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= self.profit_max_thresholds[6]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.short_rebuy_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [f"exit_profit_{self.short_rebuy_mode_name}_max"]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Short Exit High Profit
  # ---------------------------------------------------------------------------------------------
  def short_exit_high_profit(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.short_exit_signals(
      self.short_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.short_exit_main(
        self.short_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.short_exit_williams_r(
        self.short_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.short_exit_stoploss(
        self.short_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )
    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.short_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_mode_name}_stoploss_doom",
        f"exit_{self.short_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= self.profit_max_thresholds[8]:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.short_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [
      f"exit_profit_{self.short_mode_name}_max",
      f"exit_{self.short_mode_name}_stoploss_doom",
      f"exit_{self.short_mode_name}_stoploss_u_e",
    ]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Short Exit Rapid
  # ---------------------------------------------------------------------------------------------
  def short_exit_rapid(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    sell = False

    # Original sell signals
    sell, signal_name = self.short_exit_signals(
      self.short_rapid_mode_name,
      profit_init_ratio,
      max_profit,
      max_loss,
      last_candle,
      previous_candle_1,
      previous_candle_2,
      previous_candle_3,
      previous_candle_4,
      previous_candle_5,
      trade,
      current_time,
      enter_tags,
    )

    # Main sell signals
    if not sell:
      sell, signal_name = self.short_exit_main(
        self.short_rapid_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Williams %R based sells
    if not sell:
      sell, signal_name = self.short_exit_williams_r(
        self.short_rapid_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Downtrend/descending based sells
    if not sell:
      sell, signal_name = self.short_exit_dec(
        self.short_rapid_mode_name,
        profit_init_ratio,
        max_profit,
        max_loss,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Stoplosses
    if not sell:
      sell, signal_name = self.short_exit_stoploss(
        self.short_rapid_mode_name,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        max_profit,
        max_loss,
        filled_entries,
        filled_exits,
        last_candle,
        previous_candle_1,
        previous_candle_2,
        previous_candle_3,
        previous_candle_4,
        previous_candle_5,
        trade,
        current_time,
        enter_tags,
      )

    # Extra sell logic
    if not sell:
      if (0.09 >= profit_init_ratio > 0.01) and (last_candle["RSI_14"] < 22.0):
        sell, signal_name = True, f"exit_{self.short_rapid_mode_name}_rpd_1"

      if (0.09 >= profit_init_ratio > 0.01) and (last_candle["CTI_20"] < -0.95):
        sell, signal_name = True, f"exit_{self.short_rapid_mode_name}_rpd_2"

      if (0.09 >= profit_init_ratio > 0.01) and (last_candle["WILLR_14"] <= -0.99):
        sell, signal_name = True, f"exit_{self.short_rapid_mode_name}_rpd_3"

      # Stoplosses
      if profit_stake < -(
        filled_entries[0].cost
        * (self.stop_threshold_futures_rapid if self.is_futures_mode else self.stop_threshold_spot_rapid)
        / (trade.leverage if self.is_futures_mode else 1.0)
      ):
        sell, signal_name = True, f"exit_{self.short_rapid_mode_name}_stoploss_doom"

    # Profit Target Signal
    # Check if pair exist on target_profit_cache
    if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
      previous_rate = self.target_profit_cache.data[pair]["rate"]
      previous_profit = self.target_profit_cache.data[pair]["profit"]
      previous_sell_reason = self.target_profit_cache.data[pair]["sell_reason"]
      previous_time_profit_reached = datetime.fromisoformat(self.target_profit_cache.data[pair]["time_profit_reached"])

      sell_max, signal_name_max = self.exit_profit_target(
        self.short_rapid_mode_name,
        pair,
        trade,
        current_time,
        current_rate,
        profit_stake,
        profit_ratio,
        profit_current_stake_ratio,
        profit_init_ratio,
        last_candle,
        previous_candle_1,
        previous_rate,
        previous_profit,
        previous_sell_reason,
        previous_time_profit_reached,
        enter_tags,
      )
      if sell_max and signal_name_max is not None:
        return True, f"{signal_name_max}_m"
      if previous_sell_reason in [f"exit_{self.short_rapid_mode_name}_stoploss_u_e"]:
        if profit_ratio > (previous_profit + 0.005):
          mark_pair, mark_signal = self.mark_profit_target(
            self.short_rapid_mode_name,
            pair,
            True,
            previous_sell_reason,
            trade,
            current_time,
            current_rate,
            profit_ratio,
            last_candle,
            previous_candle_1,
          )
          if mark_pair:
            self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
      elif (profit_init_ratio > (previous_profit + 0.001)) and (
        previous_sell_reason not in [f"exit_{self.short_rapid_mode_name}_stoploss_doom"]
      ):
        # Update the target, raise it.
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_rapid_mode_name,
          pair,
          True,
          previous_sell_reason,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    # Add the pair to the list, if a sell triggered and conditions met
    if sell and signal_name is not None:
      previous_profit = None
      if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
        previous_profit = self.target_profit_cache.data[pair]["profit"]
      if signal_name in [
        f"exit_{self.short_rapid_mode_name}_stoploss_doom",
        f"exit_{self.short_rapid_mode_name}_stoploss_u_e",
      ]:
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_rapid_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
      elif (previous_profit is None) or (previous_profit < profit_init_ratio):
        mark_pair, mark_signal = self.mark_profit_target(
          self.short_rapid_mode_name,
          pair,
          sell,
          signal_name,
          trade,
          current_time,
          current_rate,
          profit_init_ratio,
          last_candle,
          previous_candle_1,
        )
        if mark_pair:
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)
        else:
          # Just sell it, without maximize
          return True, f"{signal_name}"
    else:
      if profit_init_ratio >= 0.01:
        previous_profit = None
        if self.target_profit_cache is not None and pair in self.target_profit_cache.data:
          previous_profit = self.target_profit_cache.data[pair]["profit"]
        if (previous_profit is None) or (previous_profit < profit_init_ratio):
          mark_signal = f"exit_profit_{self.short_rapid_mode_name}_max"
          self._set_profit_target(pair, mark_signal, current_rate, profit_init_ratio, current_time)

    if signal_name not in [f"exit_profit_{self.short_rapid_mode_name}_max"]:
      if sell and (signal_name is not None):
        return True, f"{signal_name}"

    return False, None

  # Short Exit Grind
  # ---------------------------------------------------------------------------------------------
  def short_exit_grind(
    self,
    pair: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    enter_tags,
  ) -> tuple:
    if len(filled_exits) > 30 and profit_init_ratio > 1.0:
      return True, f"exit_{self.short_grind_mode_name}_g"
    return False, None

  # Short Exit Signals
  # ---------------------------------------------------------------------------------------------
  def short_exit_signals(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    # Sell signal 1
    if (
      (last_candle["RSI_14"] < 16.0)
      and (last_candle["close"] < last_candle["BBL_20_2.0"])
      and (previous_candle_1["close"] < previous_candle_1["BBL_20_2.0"])
      and (previous_candle_2["close"] < previous_candle_2["BBL_20_2.0"])
      and (previous_candle_3["close"] < previous_candle_3["BBL_20_2.0"])
      and (previous_candle_4["close"] < previous_candle_4["BBL_20_2.0"])
    ):
      if last_candle["close"] < last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_1_2_1"

    # Sell signal 2
    elif (
      (last_candle["RSI_14"] < 14.0)
      and (last_candle["close"] < last_candle["BBL_20_2.0"])
      and (previous_candle_1["close"] < previous_candle_1["BBL_20_2.0"])
      and (previous_candle_2["close"] < previous_candle_2["BBL_20_2.0"])
    ):
      if last_candle["close"] < last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_2_2_1"

    # Sell signal 3
    elif last_candle["RSI_14"] < 12.0:
      if last_candle["close"] < last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_3_2_1"

    # Sell signal 4
    elif (last_candle["RSI_14"] < 16.0) and (last_candle["RSI_14_1h"] < 20.0):
      if last_candle["close"] < last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_4_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_4_2_1"

    # Sell signal 6
    elif (
      (last_candle["close"] > last_candle["EMA_200"])
      and (last_candle["close"] < last_candle["EMA_50"])
      and (last_candle["RSI_14"] < 21.0)
    ):
      if current_profit > 0.01:
        return True, f"exit_{mode_name}_6_1"

    # # Sell signal 7
    # elif (last_candle["RSI_14_1h"] < 21.0) and (last_candle["crossed_above_EMA_12_26"]):
    #   if last_candle["close"] < last_candle["EMA_200"]:
    #     if current_profit > 0.01:
    #       return True, f"exit_{mode_name}_7_1_1"
    #   else:
    #     if current_profit > 0.01:
    #       return True, f"exit_{mode_name}_7_2_1"

    # Sell signal 8
    elif last_candle["close"] < last_candle["BBL_20_2.0_1h"] * 0.86:
      if last_candle["close"] < last_candle["EMA_200"]:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_8_1_1"
      else:
        if current_profit > 0.01:
          return True, f"exit_{mode_name}_8_2_1"

    return False, None

  # Short Exit Main
  # ---------------------------------------------------------------------------------------------
  def short_exit_main(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if last_candle["close"] < last_candle["EMA_200"]:
      if 0.01 > current_profit >= 0.001:
        if last_candle["RSI_14"] > 90.0:
          return True, f"exit_{mode_name}_o_0"
      elif 0.02 > current_profit >= 0.01:
        if last_candle["RSI_14"] > 72.0:
          return True, f"exit_{mode_name}_o_1"
      elif 0.03 > current_profit >= 0.02:
        if last_candle["RSI_14"] > 70.0:
          return True, f"exit_{mode_name}_o_2"
      elif 0.04 > current_profit >= 0.03:
        if last_candle["RSI_14"] > 68.0:
          return True, f"exit_{mode_name}_o_3"
      elif 0.05 > current_profit >= 0.04:
        if last_candle["RSI_14"] > 66.0:
          return True, f"exit_{mode_name}_o_4"
      elif 0.06 > current_profit >= 0.05:
        if last_candle["RSI_14"] > 64.0:
          return True, f"exit_{mode_name}_o_5"
      elif 0.07 > current_profit >= 0.06:
        if last_candle["RSI_14"] > 62.0:
          return True, f"exit_{mode_name}_o_6"
      elif 0.08 > current_profit >= 0.07:
        if last_candle["RSI_14"] > 60.0:
          return True, f"exit_{mode_name}_o_7"
      elif 0.09 > current_profit >= 0.08:
        if last_candle["RSI_14"] > 58.0:
          return True, f"exit_{mode_name}_o_8"
      elif 0.1 > current_profit >= 0.09:
        if last_candle["RSI_14"] > 56.0:
          return True, f"exit_{mode_name}_o_9"
      elif 0.12 > current_profit >= 0.1:
        if last_candle["RSI_14"] > 54.0:
          return True, f"exit_{mode_name}_o_10"
      elif 0.2 > current_profit >= 0.12:
        if last_candle["RSI_14"] > 56.0:
          return True, f"exit_{mode_name}_o_11"
      elif current_profit >= 0.2:
        if last_candle["RSI_14"] > 58.0:
          return True, f"exit_{mode_name}_o_12"
    elif last_candle["close"] > last_candle["EMA_200"]:
      if 0.01 > current_profit >= 0.001:
        if last_candle["RSI_14"] > 88.0:
          return True, f"exit_{mode_name}_u_0"
      elif 0.02 > current_profit >= 0.01:
        if last_candle["RSI_14"] > 70.0:
          return True, f"exit_{mode_name}_u_1"
      elif 0.03 > current_profit >= 0.02:
        if last_candle["RSI_14"] > 68.0:
          return True, f"exit_{mode_name}_u_2"
      elif 0.04 > current_profit >= 0.03:
        if last_candle["RSI_14"] > 66.0:
          return True, f"exit_{mode_name}_u_3"
      elif 0.05 > current_profit >= 0.04:
        if last_candle["RSI_14"] > 64.0:
          return True, f"exit_{mode_name}_u_4"
      elif 0.06 > current_profit >= 0.05:
        if last_candle["RSI_14"] > 62.0:
          return True, f"exit_{mode_name}_u_5"
      elif 0.07 > current_profit >= 0.06:
        if last_candle["RSI_14"] > 60.0:
          return True, f"exit_{mode_name}_u_6"
      elif 0.08 > current_profit >= 0.07:
        if last_candle["RSI_14"] > 58.0:
          return True, f"exit_{mode_name}_u_7"
      elif 0.09 > current_profit >= 0.08:
        if last_candle["RSI_14"] > 56.0:
          return True, f"exit_{mode_name}_u_8"
      elif 0.1 > current_profit >= 0.09:
        if last_candle["RSI_14"] > 54.0:
          return True, f"exit_{mode_name}_u_9"
      elif 0.12 > current_profit >= 0.1:
        if last_candle["RSI_14"] > 52.0:
          return True, f"exit_{mode_name}_u_10"
      elif 0.2 > current_profit >= 0.12:
        if last_candle["RSI_14"] > 54.0:
          return True, f"exit_{mode_name}_u_11"
      elif current_profit >= 0.2:
        if last_candle["RSI_14"] > 56.0:
          return True, f"exit_{mode_name}_u_12"

    return False, None

  # Short Exit Based on Williams R
  # ---------------------------------------------------------------------------------------------
  def short_exit_williams_r(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if 0.01 > current_profit >= 0.001:
      if (last_candle["WILLR_480"] < -99.9) and (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 25.0):
        return True, f"exit_{mode_name}_w_0_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 16.0):
        return True, f"exit_{mode_name}_w_0_2"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] > 60.0):
        return True, f"exit_{mode_name}_w_0_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 22.0) and (last_candle["WILLR_480_1h"] < -80.0)
      ):
        return True, f"exit_{mode_name}_w_0_4"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 25.0) and (last_candle["CTI_20"] < -0.97):
        return True, f"exit_{mode_name}_w_0_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 25.0)
        and (last_candle["WILLR_480_1h"] < -95.0)
        and (last_candle["WILLR_480_4h"] < -95.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_0_6"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 25.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_0_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_0_8"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 18.0)
        and (last_candle["RSI_14_15m"] <= 28.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_0_9"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_0_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 26.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_0_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_0_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_0_13"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_0_14"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_0_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_0_16"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_0_17"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_0_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_0_19"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_0_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["RSI_14_15m"] <= 25.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_0_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["RSI_14_15m"] <= 25.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_0_22"
    elif 0.02 > current_profit >= 0.01:
      if last_candle["WILLR_480"] < -99.8:
        return True, f"exit_{mode_name}_w_1_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 22.0):
        return True, f"exit_{mode_name}_w_1_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 54.0):
        return True, f"exit_{mode_name}_w_1_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 26.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_1_4"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_1_5"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] < 30.0)
        and (last_candle["WILLR_480_1h"] < -90.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_1_6"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_1_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_1_8"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_1_9"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_1_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_1_11"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_1_12"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_1_13"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_1_14"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_1_15"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_1_16"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_1_17"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_1_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_1_19"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_1_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_1_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_1_22"
    elif 0.03 > current_profit >= 0.02:
      if last_candle["WILLR_480"] < -99.7:
        return True, f"exit_{mode_name}_w_2_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 23.0):
        return True, f"exit_{mode_name}_w_2_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 52.0):
        return True, f"exit_{mode_name}_w_2_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 27.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_2_4"
      elif (last_candle["WILLR_14"] <= -97.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_2_5"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -80.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_2_6"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_2_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_2_8"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 32.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_2_9"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_2_10"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_2_11"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_2_12"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_2_13"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_2_14"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_2_15"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_2_16"
      elif (
        (last_candle["WILLR_14"] <= -82.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_2_17"
      elif (
        (last_candle["WILLR_14"] <= -95.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_2_18"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_2_19"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_2_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_2_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_2_22"
    elif 0.04 > current_profit >= 0.03:
      if last_candle["WILLR_480"] < -99.6:
        return True, f"exit_{mode_name}_w_3_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 24.0):
        return True, f"exit_{mode_name}_w_3_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 50.0):
        return True, f"exit_{mode_name}_w_3_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 28.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_3_4"
      elif (last_candle["WILLR_14"] <= -96.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_3_5"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -80.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_3_6"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_3_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_3_8"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 34.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_3_9"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_3_10"
      elif (
        (last_candle["WILLR_14"] <= -97.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_3_11"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_3_12"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_3_13"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_3_14"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_3_15"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_3_16"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_3_17"
      elif (
        (last_candle["WILLR_14"] <= -65.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_3_18"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_3_19"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_3_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_3_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_3_22"
    elif 0.05 > current_profit >= 0.04:
      if last_candle["WILLR_480"] < -99.5:
        return True, f"exit_{mode_name}_w_4_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 25.0):
        return True, f"exit_{mode_name}_w_4_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 48.0):
        return True, f"exit_{mode_name}_w_4_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 29.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_4_4"
      elif (last_candle["WILLR_14"] <= -95.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_4_5"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -80.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_4_6"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_4_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_4_8"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 36.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_4_9"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_4_10"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_4_11"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_4_12"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_4_13"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_4_14"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_4_15"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_4_16"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_4_17"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_4_18"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_4_19"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_4_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_4_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_4_22"
    elif 0.06 > current_profit >= 0.05:
      if last_candle["WILLR_480"] < -99.4:
        return True, f"exit_{mode_name}_w_5_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 26.0):
        return True, f"exit_{mode_name}_w_5_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 46.0):
        return True, f"exit_{mode_name}_w_5_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 30.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_5_4"
      elif (last_candle["WILLR_14"] <= -94.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_5_5"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -80.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_5_6"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_5_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_5_8"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 38.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_5_9"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_5_10"
      elif (
        (last_candle["WILLR_14"] <= -95.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_5_11"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_5_12"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_5_13"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_5_14"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_5_15"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_5_16"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_5_17"
      elif (
        (last_candle["WILLR_14"] <= -55.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_5_18"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_5_19"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_5_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 38.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_5_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_5_22"
    elif 0.07 > current_profit >= 0.06:
      if last_candle["WILLR_480"] < -99.3:
        return True, f"exit_{mode_name}_w_6_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 25.0):
        return True, f"exit_{mode_name}_w_6_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 48.0):
        return True, f"exit_{mode_name}_w_6_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 29.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_6_4"
      elif (last_candle["WILLR_14"] <= -95.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_6_5"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -80.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_6_6"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_6_7"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_6_8"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 36.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_6_9"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_6_10"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_6_11"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_6_12"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_6_13"
      elif (
        (last_candle["WILLR_14"] <= -82.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_6_14"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_6_15"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_6_16"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_6_17"
      elif (
        (last_candle["WILLR_14"] <= -65.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_6_18"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_6_19"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_6_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_6_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_6_22"
    elif 0.08 > current_profit >= 0.07:
      if last_candle["WILLR_480"] < -99.5:
        return True, f"exit_{mode_name}_w_7_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 24.0):
        return True, f"exit_{mode_name}_w_7_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 50.0):
        return True, f"exit_{mode_name}_w_7_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 28.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_7_4"
      elif (last_candle["WILLR_14"] <= -96.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_7_5"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -85.0)
        and (last_candle["WILLR_480_4h"] < -90.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_7_6"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_7_7"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_7_8"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 34.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_7_9"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_7_10"
      elif (
        (last_candle["WILLR_14"] <= -97.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_7_11"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_7_12"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_7_13"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_7_14"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_7_15"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_7_16"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_7_17"
      elif (
        (last_candle["WILLR_14"] <= -75.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_7_18"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_7_19"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_7_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_7_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_7_22"
    elif 0.09 > current_profit >= 0.08:
      if last_candle["WILLR_480"] < -99.6:
        return True, f"exit_{mode_name}_w_8_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 23.0):
        return True, f"exit_{mode_name}_w_8_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 52.0):
        return True, f"exit_{mode_name}_w_8_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 27.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_8_4"
      elif (last_candle["WILLR_14"] <= -97.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_8_5"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -85.0)
        and (last_candle["WILLR_480_4h"] < -90.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_8_6"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_8_7"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_8_8"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 32.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_8_9"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_8_10"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_8_11"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_8_12"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_8_13"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_8_14"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_8_15"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_8_16"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_8_17"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_8_18"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_8_19"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_8_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_8_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_8_22"
    elif 0.1 > current_profit >= 0.09:
      if last_candle["WILLR_480"] < -99.7:
        return True, f"exit_{mode_name}_w_9_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 22.0):
        return True, f"exit_{mode_name}_w_9_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 54.0):
        return True, f"exit_{mode_name}_w_9_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 26.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_9_4"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_9_5"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -85.0)
        and (last_candle["WILLR_480_4h"] < -90.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_9_6"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] < 40.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_9_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_9_8"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_9_9"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_9_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_9_11"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_9_12"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_9_13"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_9_14"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_9_15"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_9_16"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_9_17"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_9_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_9_19"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_9_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_9_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_9_22"
    elif 0.12 > current_profit >= 0.1:
      if last_candle["WILLR_480"] > -99.8:
        return True, f"exit_{mode_name}_w_10_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] > 79.0):
        return True, f"exit_{mode_name}_w_10_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] < 44.0):
        return True, f"exit_{mode_name}_w_10_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 25.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_10_4"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_10_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 35.0)
        and (last_candle["WILLR_480_1h"] < -90.0)
        and (last_candle["WILLR_480_4h"] < -95.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_10_6"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 35.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_10_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_10_8"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] <= 28.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_10_9"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_10_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 28.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_10_11"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_10_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_10_13"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_10_14"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_10_15"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_10_16"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_10_17"
      elif (
        (last_candle["WILLR_14"] <= -95.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_10_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_10_19"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_10_20"
      elif (
        (last_candle["WILLR_14"] >= -99.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_10_21"
      elif (
        (last_candle["WILLR_14"] >= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_10_22"
    elif 0.2 > current_profit >= 0.12:
      if last_candle["WILLR_480"] < -99.6:
        return True, f"exit_{mode_name}_w_11_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 20.0):
        return True, f"exit_{mode_name}_w_11_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 58.0):
        return True, f"exit_{mode_name}_w_11_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 24.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_11_4"
      elif (last_candle["WILLR_14"] <= -99.5) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_11_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 30.0)
        and (last_candle["WILLR_480_1h"] < -90.0)
        and (last_candle["WILLR_480_4h"] < -95.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_11_6"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 30.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_11_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_11_8"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] <= 26.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_11_9"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_11_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 26.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_11_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_11_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_11_13"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_11_14"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_11_15"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_11_16"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_11_17"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_11_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 35.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_11_19"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_11_20"
      elif (
        (last_candle["WILLR_14"] >= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_11_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 25.0)
        and (last_candle["RSI_14_15m"] <= 35.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_11_22"
    elif current_profit >= 0.2:
      if last_candle["WILLR_480"] < -99.8:
        return True, f"exit_{mode_name}_w_12_1"
      elif (last_candle["WILLR_14"] <= -99.0) and (last_candle["RSI_14"] < 19.0):
        return True, f"exit_{mode_name}_w_12_2"
      elif (last_candle["WILLR_14"] <= -98.0) and (last_candle["RSI_14"] > 60.0):
        return True, f"exit_{mode_name}_w_12_3"
      elif (
        (last_candle["WILLR_14"] <= -95.0) and (last_candle["RSI_14"] < 23.0) and (last_candle["WILLR_480_1h"] < -75.0)
      ):
        return True, f"exit_{mode_name}_w_12_4"
      elif (last_candle["WILLR_14"] <= -0.99) and (last_candle["CTI_20"] < -0.95):
        return True, f"exit_{mode_name}_w_12_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 25.0)
        and (last_candle["WILLR_480_1h"] < -95.0)
        and (last_candle["WILLR_480_4h"] < -95.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 40.0)
        and (last_candle["CTI_20_1d"] < -0.80)
      ):
        return True, f"exit_{mode_name}_w_12_6"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] < 25.0)
        and (last_candle["WILLR_480_1h"] < -75.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["RSI_14_1h"] < 50.0)
        and (last_candle["RSI_14_4h"] < 50.0)
        and (last_candle["RSI_14_1d"] < 50.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_12_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["RSI_14_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.02)
      ):
        return True, f"exit_{mode_name}_w_12_8"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["RSI_14_15m"] <= 24.0)
        and (last_candle["CTI_20_4h"] >= 0.50)
        and (last_candle["CTI_20_1d"] <= -0.70)
      ):
        return True, f"exit_{mode_name}_w_12_9"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_12_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["RSI_14_15m"] <= 24.0)
        and (last_candle["RSI_14_1h"] <= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["WILLR_480_1h"] < -70.0)
      ):
        return True, f"exit_{mode_name}_w_12_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["change_pct_1d"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_12_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["RSI_14_4h"] <= 35.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.01)
      ):
        return True, f"exit_{mode_name}_w_12_13"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_1h"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
      ):
        return True, f"exit_{mode_name}_w_12_14"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_4h"] <= 25.0)
        and (last_candle["WILLR_480_4h"] < -85.0)
        and (last_candle["change_pct_1h"] > 0.00)
      ):
        return True, f"exit_{mode_name}_w_12_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["bot_wick_pct_1d"] > 0.16)
        and (last_candle["close"] > (last_candle["low_min_24_1h"] * 1.20))
        and (last_candle["hl_pct_change_6_1d"] > 0.75)
      ):
        return True, f"exit_{mode_name}_w_12_16"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["WILLR_480_1h"] < -70.0)
        and (last_candle["WILLR_480_4h"] < -75.0)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["bot_wick_pct_1d"] > 0.08)
      ):
        return True, f"exit_{mode_name}_w_12_17"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.90)
      ):
        return True, f"exit_{mode_name}_w_12_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 20.0)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["hl_pct_change_48_1h"] > 0.50)
      ):
        return True, f"exit_{mode_name}_w_12_19"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 30.0)
        and (last_candle["WILLR_480_4h"] < -70.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_12_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["RSI_14_15m"] <= 25.0)
        and (last_candle["CTI_20_dec_3_1h"] == False)
        and (last_candle["WILLR_480_4h"] > -50.0)
      ):
        return True, f"exit_{mode_name}_w_12_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["RSI_14_15m"] <= 25.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_w_12_22"

    return False, None

  # Short Exit Dec
  # ---------------------------------------------------------------------------------------------
  def short_exit_dec(
    self,
    mode_name: str,
    current_profit: float,
    max_profit: float,
    max_loss: float,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    if 0.01 > current_profit >= 0.001:
      if (
        (last_candle["WILLR_14"] < -99.0)
        and (last_candle["RSI_14"] < 30.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_0_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_0_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_4"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 5.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_6"
      elif (
        (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_8"
      elif (
        (last_candle["RSI_14"] >= 80.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_9"
      elif (
        (last_candle["RSI_14"] >= 80.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_0_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_13"
      elif (
        (last_candle["RSI_14"] >= 70.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_14"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_16"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_0_17"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_0_19"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_0_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_0_22"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_0_23"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 5.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] <= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_0_24"
      elif (
        (last_candle["WILLR_14"] >= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_0_25"
    elif 0.02 > current_profit >= 0.01:
      if (
        (last_candle["WILLR_14"] < -90.0)
        and (last_candle["RSI_14"] < 34.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_1_1"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_1_2"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_3"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_4"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_5"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_6"
      elif (
        (last_candle["RSI_3"] <= 40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_8"
      elif (
        (last_candle["RSI_14"] >= 70.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_9"
      elif (
        (last_candle["RSI_14"] >= 54.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_1_10"
      elif (
        (last_candle["WILLR_14"] <= -95.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_11"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_12"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_13"
      elif (
        (last_candle["RSI_14"] >= 54.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_14"
      elif (
        (last_candle["WILLR_14"] <= -95.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_15"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_16"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_1_17"
      elif (
        (last_candle["WILLR_14"] <= -40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_18"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_1_19"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_20"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_1_21"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_1_22"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_1_23"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_1_24"
      elif (
        (last_candle["WILLR_14"] <= -75.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_1_25"
    elif 0.03 > current_profit >= 0.02:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 44.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_2_1"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_2_2"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_2_3"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_2_4"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_5"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_6"
      elif (
        (last_candle["RSI_3"] <= 40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_8"
      elif (
        (last_candle["RSI_14"] >= 60.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_9"
      elif (
        (last_candle["RSI_14"] <= 48.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_2_10"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_2_11"
      elif (
        (last_candle["WILLR_14"] <= -91.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_12"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_13"
      elif (
        (last_candle["RSI_14"] <= 48.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_14"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_2_15"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_2_16"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_2_17"
      elif (
        (last_candle["WILLR_14"] <= -40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_18"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_2_19"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_2_20"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_2_21"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_2_22"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_2_23"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_24"
      elif (
        (last_candle["WILLR_14"] <= -75.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_2_25"
    elif 0.04 > current_profit >= 0.03:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 46.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_3_1"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_3_2"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_3"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_4"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_5"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_6"
      elif (
        (last_candle["RSI_3"] <= 40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_8"
      elif (
        (last_candle["RSI_14"] >= 58.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_9"
      elif (
        (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_3_10"
      elif (
        (last_candle["WILLR_14"] <= -93.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_11"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_12"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_13"
      elif (
        (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_14"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_15"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_16"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_3_17"
      elif (
        (last_candle["WILLR_14"] <= -40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_18"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_3_19"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_20"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_3_21"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_3_22"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_3_23"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 20.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_3_24"
      elif (
        (last_candle["WILLR_14"] <= -75.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_3_25"
    elif 0.05 > current_profit >= 0.04:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 48.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_4_1"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_4_2"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_3"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_4"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_5"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_6"
      elif (
        (last_candle["RSI_3"] <= 40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 38.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_8"
      elif (
        (last_candle["RSI_14"] <= 44.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_9"
      elif (
        (last_candle["RSI_14"] >= 48.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_4_10"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_11"
      elif (
        (last_candle["WILLR_14"] >= -11.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_12"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_13"
      elif (
        (last_candle["RSI_14"] >= 48.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_14"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_15"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_16"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_4_17"
      elif (
        (last_candle["WILLR_14"] <= -40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_18"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_4_19"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_20"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_4_21"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_4_22"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_4_23"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_4_24"
      elif (
        (last_candle["WILLR_14"] <= -75.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_4_25"
    elif 0.06 > current_profit >= 0.05:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_5_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_5_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_4"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_5"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_6"
      elif (
        (last_candle["RSI_3"] <= 40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_7"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_8"
      elif (
        (last_candle["RSI_14"] >= 54.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_9"
      elif (
        (last_candle["RSI_14"] >= 46.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_5_10"
      elif (
        (last_candle["WILLR_14"] <= -91.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_11"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_12"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_13"
      elif (
        (last_candle["RSI_14"] >= 46.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_14"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_15"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_16"
      elif (
        (last_candle["WILLR_14"] <= -76.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_5_17"
      elif (
        (last_candle["WILLR_14"] <= -40.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_18"
      elif (
        (last_candle["WILLR_14"] <= -60.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_5_19"
      elif (
        (last_candle["WILLR_14"] <= -70.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_20"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_5_21"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_5_22"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_5_23"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_5_24"
      elif (
        (last_candle["WILLR_14"] <= -75.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_5_25"
    elif 0.07 > current_profit >= 0.06:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_6_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_6_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_4"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_3"] <= 6.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_5"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_6"
      elif (
        (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_7"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 38.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_8"
      elif (
        (last_candle["RSI_14"] <= 44.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_9"
      elif (
        (last_candle["RSI_14"] >= 48.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_6_10"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_11"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_12"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_13"
      elif (
        (last_candle["RSI_14"] >= 48.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_14"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_15"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_16"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_6_17"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_18"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_6_19"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_20"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_6_21"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_6_22"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_6_23"
      elif (
        (last_candle["WILLR_14"] <= -84.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_6_24"
      elif (
        (last_candle["WILLR_14"] <= -80.0)
        and (last_candle["RSI_14"] <= 38.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 26.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_6_25"
    elif 0.08 > current_profit >= 0.07:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_7_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_7_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_4"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_3"] <= 4.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_5"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_6"
      elif (
        (last_candle["RSI_3"] <= 5.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_7"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_8"
      elif (
        (last_candle["RSI_14"] <= 42.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_9"
      elif (
        (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_7_10"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_11"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_12"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_13"
      elif (
        (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_14"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_15"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_16"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_14"] <= 38.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_7_17"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_18"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_7_19"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_20"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_7_21"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_7_22"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_7_23"
      elif (
        (last_candle["WILLR_14"] <= -86.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_7_24"
      elif (
        (last_candle["WILLR_14"] <= -85.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_7_25"
    elif 0.09 > current_profit >= 0.08:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_8_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_8_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_4"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_5"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_3"] <= 5.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_6"
      elif (
        (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_7"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_8"
      elif (
        (last_candle["RSI_14"] >= 60.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_9"
      elif (
        (last_candle["RSI_14"] <= 48.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_8_10"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_11"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_12"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_13"
      elif (
        (last_candle["RSI_14"] <= 48.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_14"
      elif (
        (last_candle["WILLR_14"] <= -95.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_15"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_16"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_8_17"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_18"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_8_19"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_20"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_8_21"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_8_22"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_8_23"
      elif (
        (last_candle["WILLR_14"] <= -88.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_8_24"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_8_25"
    elif 0.1 > current_profit >= 0.09:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 48.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_9_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_9_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_4"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.70)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_6"
      elif (
        (last_candle["RSI_3"] >= 99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_8"
      elif (
        (last_candle["RSI_14"] <= 38.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_9"
      elif (
        (last_candle["RSI_14"] >= 54.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_9_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 36.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_11"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_12"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_13"
      elif (
        (last_candle["RSI_14"] >= 54.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_14"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_16"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 34.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_9_17"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_18"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_9_19"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_20"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_9_21"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_9_22"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_9_23"
      elif (
        (last_candle["WILLR_14"] <= -90.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_9_24"
      elif (
        (last_candle["WILLR_14"] <= -92.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_9_25"
    elif 0.12 > current_profit >= 0.1:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 46.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_10_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_10_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_4"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_6"
      elif (
        (last_candle["RSI_3"] >= 99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_8"
      elif (
        (last_candle["RSI_14"] >= 64.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_9"
      elif (
        (last_candle["RSI_14"] <= 44.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_10_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_12"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_13"
      elif (
        (last_candle["RSI_14"] <= 44.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_14"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_16"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 32.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_10_17"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_18"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_10_19"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_20"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_10_21"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_10_22"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_10_23"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_10_24"
      elif (
        (last_candle["WILLR_14"] <= -94.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_10_25"
    elif 0.2 > current_profit >= 0.12:
      if (
        (last_candle["WILLR_14"] < -84.0)
        and (last_candle["RSI_14"] < 44.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_11_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_11_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_4"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_6"
      elif (
        (last_candle["RSI_3"] <= 1.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_8"
      elif (
        (last_candle["RSI_14"] >= 66.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_9"
      elif (
        (last_candle["RSI_14"] >= 60.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_11_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_13"
      elif (
        (last_candle["RSI_14"] <= 42.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_14"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_16"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_11_17"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_18"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_11_19"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_20"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_11_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_11_22"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_11_23"
      elif (
        (last_candle["WILLR_14"] <= -96.0)
        and (last_candle["RSI_3"] <= 20.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_11_24"
      elif (
        (last_candle["WILLR_14"] <= -98.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_11_25"
    elif current_profit >= 0.2:
      if (
        (last_candle["WILLR_14"] < -90.0)
        and (last_candle["RSI_14"] < 34.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_12_1"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["EMA_200_dec_4_1d"] == False)
        and (last_candle["change_pct_4h"] > 0.03)
      ):
        return True, f"exit_{mode_name}_d_12_2"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_14_4h"] <= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_4h"] >= 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_3"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 10.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] > -25.0)
        and (last_candle["CTI_20_1d"] < -0.50)
        and (last_candle["RSI_14_1d"] <= 30.0)
        and (last_candle["change_pct_1h"] > 0.03)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_4"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["change_pct_1d"] > 0.02)
        and (last_candle["change_pct_4h"] > 0.02)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_5"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 2.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.80)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_6"
      elif (
        (last_candle["RSI_3"] >= 99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_4h"] <= -0.50)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_24"] == False)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_7"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["WILLR_480_4h"] > -10.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_8"
      elif (
        (last_candle["RSI_14"] >= 70.0)
        and (last_candle["RSI_3_1h"] >= 90.0)
        and (last_candle["RSI_3_4h"] >= 94.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_9"
      elif (
        (last_candle["RSI_14"] >= 64.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["RSI_14_4h"] <= 40.0)
        and (last_candle["change_pct_1h"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_12_10"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["change_pct_1d"] > 0.10)
        and (last_candle["not_downtrend_4h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_11"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 20.0)
        and (last_candle["CTI_20_1d"] <= -0.80)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_12"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 26.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["change_pct_4h"] > 0.03)
        and (last_candle["bot_wick_pct_4h"] > 0.03)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_13"
      elif (
        (last_candle["RSI_14"] >= 60.0)
        and (last_candle["RSI_14_15m"] >= 60.0)
        and (last_candle["RSI_3_1d"] >= 94.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_14"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 24.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["WILLR_480_4h"] <= -70.0)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_15"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["CTI_20_1d"] <= -0.70)
        and (last_candle["change_pct_1d"] > 0.04)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_16"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 28.0)
        and (last_candle["RSI_14_15m"] <= 40.0)
        and (last_candle["RSI_14_1h"] <= 40.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["WILLR_480_4h"] > -30.0)
        and (last_candle["change_pct_1d"] > 0.04)
      ):
        return True, f"exit_{mode_name}_d_12_17"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_24_15m"] == False)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_24_4h"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_18"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_max_6_1d"] <= 15.0)
        and (last_candle["change_pct_1h"] > 0.01)
        and (last_candle["change_pct_4h"] > 0.06)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_12_19"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_1d"] <= 30.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_20"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 50.0)
        and (last_candle["CTI_20_dec_3_1d"] == False)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["close"] > (last_candle["low_min_48_1h"] * 1.25))
      ):
        return True, f"exit_{mode_name}_d_12_21"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 40.0)
        and (last_candle["RSI_14_max_6_4h"] <= 30.0)
        and (last_candle["change_pct_4h"] > 0.01)
        and (last_candle["not_downtrend_4h"] == True)
        and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.30))
      ):
        return True, f"exit_{mode_name}_d_12_22"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 30.0)
        and (last_candle["not_downtrend_1h"] == True)
        and (last_candle["not_downtrend_1d"] == True)
        and (last_candle["close"] > (last_candle["low_min_6_1d"] * 1.20))
      ):
        return True, f"exit_{mode_name}_d_12_23"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_3"] <= 5.0)
        and (last_candle["RSI_14"] >= 50.0)
        and (last_candle["RSI_14_15m"] >= 50.0)
        and (last_candle["RSI_3_1h"] >= 80.0)
        and (last_candle["change_pct_1h"] > 0.02)
        and (last_candle["not_downtrend_1h"] == True)
      ):
        return True, f"exit_{mode_name}_d_12_24"
      elif (
        (last_candle["WILLR_14"] <= -99.0)
        and (last_candle["RSI_14"] <= 22.0)
        and (last_candle["RSI_14_15m"] <= 50.0)
        and (last_candle["RSI_14_1d"] <= 50.0)
        and (last_candle["RSI_3_1d"] >= 74.0)
        and (last_candle["EMA_200_dec_48_1h"] == False)
        and (last_candle["EMA_200_dec_4_1d"] == False)
      ):
        return True, f"exit_{mode_name}_d_12_25"

    return False, None

  # Short Exit Stop Loss
  # ---------------------------------------------------------------------------------------------
  def short_exit_stoploss(
    self,
    mode_name: str,
    current_rate: float,
    profit_stake: float,
    profit_ratio: float,
    profit_current_stake_ratio: float,
    profit_init_ratio: float,
    max_profit: float,
    max_loss: float,
    filled_entries,
    filled_exits,
    last_candle,
    previous_candle_1,
    previous_candle_2,
    previous_candle_3,
    previous_candle_4,
    previous_candle_5,
    trade: "Trade",
    current_time: "datetime",
    buy_tag,
  ) -> tuple:
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]
    # Stoploss doom
    if (
      self.is_futures_mode is False
      and profit_stake
      < -(filled_entries[0].cost * self.stop_threshold / (trade.leverage if self.is_futures_mode else 1.0))
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 6, 13) or is_backtest)
    ):
      return True, f"exit_{mode_name}_stoploss"

    if (
      self.is_futures_mode is True
      and profit_stake
      < -(filled_entries[0].cost * self.stop_threshold_futures / (trade.leverage if self.is_futures_mode else 1.0))
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 10, 17) or is_backtest)
    ):
      return True, f"exit_{mode_name}_stoploss"

    return False, None

    #

  #   ______  __    __  ______  _______ ________         ______  _______  ______ __    __ _______
  #  /      \|  \  |  \/      \|       |        \       /      \|       \|      |  \  |  |       \
  # |  $$$$$$| $$  | $|  $$$$$$| $$$$$$$\$$$$$$$$      |  $$$$$$| $$$$$$$\\$$$$$| $$\ | $| $$$$$$$\
  # | $$___\$| $$__| $| $$  | $| $$__| $$ | $$         | $$ __\$| $$__| $$ | $$ | $$$\| $| $$  | $$
  #  \$$    \| $$    $| $$  | $| $$    $$ | $$         | $$|    | $$    $$ | $$ | $$$$\ $| $$  | $$
  #  _\$$$$$$| $$$$$$$| $$  | $| $$$$$$$\ | $$         | $$ \$$$| $$$$$$$\ | $$ | $$\$$ $| $$  | $$
  # |  \__| $| $$  | $| $$__/ $| $$  | $$ | $$         | $$__| $| $$  | $$_| $$_| $$ \$$$| $$__/ $$
  #  \$$    $| $$  | $$\$$    $| $$  | $$ | $$          \$$    $| $$  | $|   $$ | $$  \$$| $$    $$
  #   \$$$$$$ \$$   \$$ \$$$$$$ \$$   \$$  \$$           \$$$$$$ \$$   \$$\$$$$$$\$$   \$$\$$$$$$$
  #

  ###############################################################################################
  # SHORT GRIND FUNCTIONS STARTS HERE
  ###############################################################################################

  # Short Grinding Adjust Trade Position
  # ---------------------------------------------------------------------------------------------
  def short_grind_adjust_trade_position(
    self,
    trade: Trade,
    enter_tags,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ):
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]
    # min/max stakes include leverage. The return amounts is before leverage.
    min_stake /= trade.leverage
    max_stake /= trade.leverage
    df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
    if len(df) < 2:
      return None
    last_candle = df.iloc[-1].squeeze()
    previous_candle = df.iloc[-2].squeeze()

    filled_orders = trade.select_filled_orders()
    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)
    count_of_entries = trade.nr_of_successful_entries
    count_of_exits = trade.nr_of_successful_exits

    if count_of_entries == 0:
      return None

    if len(filled_orders) < 1:
      return None
    has_order_tags = False
    if hasattr(filled_orders[0], "ft_order_tag"):
      has_order_tags = True

    exit_rate = current_rate
    if self.dp.runmode.value in ("live", "dry_run"):
      ticker = self.dp.ticker(trade.pair)
      if ("bid" in ticker) and ("ask" in ticker):
        if trade.is_short:
          if self.config["exit_pricing"]["price_side"] in ["ask", "other"]:
            if ticker["ask"] is not None:
              exit_rate = ticker["ask"]
        else:
          if self.config["exit_pricing"]["price_side"] in ["bid", "other"]:
            if ticker["bid"] is not None:
              exit_rate = ticker["bid"]

    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, exit_rate
    )

    slice_amount = filled_entries[0].cost
    slice_profit = (exit_rate - filled_orders[-1].safe_price) / filled_orders[-1].safe_price
    slice_profit_entry = (exit_rate - filled_entries[-1].safe_price) / filled_entries[-1].safe_price
    slice_profit_exit = (
      ((exit_rate - filled_exits[-1].safe_price) / filled_exits[-1].safe_price) if count_of_exits > 0 else 0.0
    )

    current_stake_amount = trade.amount * current_rate
    is_derisk = trade.amount < (filled_entries[0].safe_filled * 0.95)
    is_derisk_calc = False
    is_rebuy_mode = all(c in self.short_rebuy_mode_tags for c in enter_tags) or (
      any(c in self.short_rebuy_mode_tags for c in enter_tags)
      and all(c in (self.short_rebuy_mode_tags + self.short_grind_mode_tags) for c in enter_tags)
    )
    is_grind_mode = all(c in self.short_grind_mode_tags for c in enter_tags)

    fee_open_rate = trade.fee_open if self.custom_fee_open_rate is None else self.custom_fee_open_rate
    fee_close_rate = trade.fee_close if self.custom_fee_close_rate is None else self.custom_fee_close_rate

    # Rebuy mode
    if is_rebuy_mode:
      slice_amount /= self.rebuy_mode_stake_multiplier
    # Grind mode
    elif is_grind_mode:
      slice_amount /= (
        self.grind_mode_stake_multiplier_futures[0]
        if self.is_futures_mode
        else self.grind_mode_stake_multiplier_spot[0]
      )
    elif not is_derisk and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 2, 5) or is_backtest):
      rebuy_stake, order_tag, is_derisk_calc = self.short_adjust_trade_position_no_derisk(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
        last_candle,
        previous_candle,
        filled_orders,
        filled_entries,
        filled_exits,
        exit_rate,
        slice_amount,
        slice_profit_entry,
        slice_profit,
        profit_ratio,
        profit_stake,
        profit_init_ratio,
        current_stake_amount,
        has_order_tags,
      )
      if rebuy_stake is not None:
        if has_order_tags:
          return rebuy_stake, order_tag
        else:
          return rebuy_stake
      elif count_of_exits == 0:
        return None
      elif not is_derisk_calc:
        return None

    if not is_rebuy_mode and not is_grind_mode:
      # First entry is lower now, therefore the grinds must adjust
      if trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 2, 5) or is_backtest:
        slice_amount /= (
          self.regular_mode_stake_multiplier_futures[0]
          if self.is_futures_mode
          else self.regular_mode_stake_multiplier_spot[0]
        )

    grind_derisk = self.grind_derisk_futures if self.is_futures_mode else self.grind_derisk_spot

    grind_1_max_sub_grinds = 0
    grind_1_stakes = self.grind_1_stakes_futures.copy() if self.is_futures_mode else self.grind_1_stakes_spot.copy()
    grind_1_sub_thresholds = (
      self.grind_1_sub_thresholds_futures if self.is_futures_mode else self.grind_1_sub_thresholds_spot
    )
    if (slice_amount * grind_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_1_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_1_stakes):
        grind_1_stakes[i] *= multi
    grind_1_max_sub_grinds = len(grind_1_stakes)
    grind_1_stop_grinds = self.grind_1_stop_grinds_futures if self.is_futures_mode else self.grind_1_stop_grinds_spot
    grind_1_profit_threshold = (
      self.grind_1_profit_threshold_futures if self.is_futures_mode else self.grind_1_profit_threshold_spot
    )

    grind_2_max_sub_grinds = 0
    grind_2_stakes = self.grind_2_stakes_futures.copy() if self.is_futures_mode else self.grind_2_stakes_spot.copy()
    grind_2_sub_thresholds = (
      self.grind_2_sub_thresholds_futures if self.is_futures_mode else self.grind_2_sub_thresholds_spot
    )
    if (slice_amount * grind_2_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_2_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_2_stakes):
        grind_2_stakes[i] *= multi
    grind_2_max_sub_grinds = len(grind_2_stakes)
    grind_2_stop_grinds = self.grind_2_stop_grinds_futures if self.is_futures_mode else self.grind_2_stop_grinds_spot
    grind_2_profit_threshold = (
      self.grind_2_profit_threshold_futures if self.is_futures_mode else self.grind_2_profit_threshold_spot
    )

    grind_3_max_sub_grinds = 0
    grind_3_stakes = self.grind_3_stakes_futures.copy() if self.is_futures_mode else self.grind_3_stakes_spot.copy()
    grind_3_sub_thresholds = (
      self.grind_3_sub_thresholds_futures if self.is_futures_mode else self.grind_3_sub_thresholds_spot
    )
    if (slice_amount * grind_3_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_3_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_3_stakes):
        grind_3_stakes[i] *= multi
    grind_3_max_sub_grinds = len(grind_3_stakes)
    grind_3_stop_grinds = self.grind_3_stop_grinds_futures if self.is_futures_mode else self.grind_3_stop_grinds_spot
    grind_3_profit_threshold = (
      self.grind_3_profit_threshold_futures if self.is_futures_mode else self.grind_3_profit_threshold_spot
    )

    grind_4_max_sub_grinds = 0
    grind_4_stakes = self.grind_4_stakes_futures.copy() if self.is_futures_mode else self.grind_4_stakes_spot.copy()
    grind_4_sub_thresholds = (
      self.grind_4_sub_thresholds_futures if self.is_futures_mode else self.grind_4_sub_thresholds_spot
    )
    if (slice_amount * grind_4_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_4_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_4_stakes):
        grind_4_stakes[i] *= multi
    grind_4_max_sub_grinds = len(grind_4_stakes)
    grind_4_stop_grinds = self.grind_4_stop_grinds_futures if self.is_futures_mode else self.grind_4_stop_grinds_spot
    grind_4_profit_threshold = (
      self.grind_4_profit_threshold_futures if self.is_futures_mode else self.grind_4_profit_threshold_spot
    )

    grind_5_max_sub_grinds = 0
    grind_5_stakes = self.grind_5_stakes_futures.copy() if self.is_futures_mode else self.grind_5_stakes_spot.copy()
    grind_5_sub_thresholds = (
      self.grind_5_sub_thresholds_futures if self.is_futures_mode else self.grind_5_sub_thresholds_spot
    )
    if (slice_amount * grind_5_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_5_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_5_stakes):
        grind_5_stakes[i] *= multi
    grind_5_max_sub_grinds = len(grind_5_stakes)
    grind_5_stop_grinds = self.grind_5_stop_grinds_futures if self.is_futures_mode else self.grind_5_stop_grinds_spot
    grind_5_profit_threshold = (
      self.grind_5_profit_threshold_futures if self.is_futures_mode else self.grind_5_profit_threshold_spot
    )

    grind_6_max_sub_grinds = 0
    grind_6_stakes = self.grind_6_stakes_futures.copy() if self.is_futures_mode else self.grind_6_stakes_spot.copy()
    grind_6_sub_thresholds = (
      self.grind_6_sub_thresholds_futures if self.is_futures_mode else self.grind_6_sub_thresholds_spot
    )
    if (slice_amount * grind_6_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_6_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_6_stakes):
        grind_6_stakes[i] *= multi
    grind_6_max_sub_grinds = len(grind_6_stakes)
    grind_6_stop_grinds = self.grind_6_stop_grinds_futures if self.is_futures_mode else self.grind_6_stop_grinds_spot
    grind_6_profit_threshold = (
      self.grind_6_profit_threshold_futures if self.is_futures_mode else self.grind_6_profit_threshold_spot
    )

    grind_1_derisk_1_max_sub_grinds = 0
    grind_1_derisk_1_stakes = (
      self.grind_1_derisk_1_stakes_futures.copy() if self.is_futures_mode else self.grind_1_derisk_1_stakes_spot.copy()
    )
    grind_1_derisk_1_sub_thresholds = (
      self.grind_1_derisk_1_sub_thresholds_futures
      if self.is_futures_mode
      else self.grind_1_derisk_1_sub_thresholds_spot
    )
    if (slice_amount * grind_1_derisk_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_1_derisk_1_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_1_derisk_1_stakes):
        grind_1_derisk_1_stakes[i] *= multi
    grind_1_derisk_1_max_sub_grinds = len(grind_1_derisk_1_stakes)
    grind_1_derisk_1_stop_grinds = (
      self.grind_1_derisk_1_stop_grinds_futures if self.is_futures_mode else self.grind_1_derisk_1_stop_grinds_spot
    )
    grind_1_derisk_1_profit_threshold = (
      self.grind_1_derisk_1_profit_threshold_futures
      if self.is_futures_mode
      else self.grind_1_derisk_1_profit_threshold_spot
    )

    grind_2_derisk_1_max_sub_grinds = 0
    grind_2_derisk_1_stakes = (
      self.grind_2_derisk_1_stakes_futures.copy() if self.is_futures_mode else self.grind_2_derisk_1_stakes_spot.copy()
    )
    grind_2_derisk_1_sub_thresholds = (
      self.grind_2_derisk_1_sub_thresholds_futures
      if self.is_futures_mode
      else self.grind_2_derisk_1_sub_thresholds_spot
    )
    if (slice_amount * grind_2_derisk_1_stakes[0] / (trade.leverage if self.is_futures_mode else 1.0)) < min_stake:
      multi = min_stake / slice_amount / grind_2_derisk_1_stakes[0] * trade.leverage
      for i, _ in enumerate(grind_2_derisk_1_stakes):
        grind_2_derisk_1_stakes[i] *= multi
    grind_2_derisk_1_max_sub_grinds = len(grind_2_derisk_1_stakes)
    grind_2_derisk_1_stop_grinds = (
      self.grind_2_derisk_1_stop_grinds_futures if self.is_futures_mode else self.grind_2_derisk_1_stop_grinds_spot
    )
    grind_2_derisk_1_profit_threshold = (
      self.grind_2_derisk_1_profit_threshold_futures
      if self.is_futures_mode
      else self.grind_2_derisk_1_profit_threshold_spot
    )

    partial_sell = False
    is_derisk_found = False  # d de-risk
    is_derisk_1 = False
    is_derisk_1_found = False  # d1 de-risk exit
    derisk_1_order = None
    derisk_1_reentry_order = None
    derisk_1_sub_grind_count = 0
    derisk_1_total_amount = 0.0
    derisk_1_total_cost = 0.0
    derisk_1_current_open_rate = 0.0
    derisk_1_current_grind_stake = 0.0
    derisk_1_current_grind_stake_profit = 0.0
    derisk_1_is_sell_found = False
    derisk_1_reentry_found = False
    derisk_1_buy_orders = []
    derisk_1_distance_ratio = 0.0
    grind_1_sub_grind_count = 0
    grind_1_total_amount = 0.0
    grind_1_total_cost = 0.0
    grind_1_current_open_rate = 0.0
    grind_1_current_grind_stake = 0.0
    grind_1_current_grind_stake_profit = 0.0
    grind_1_is_sell_found = False
    grind_1_found = False
    grind_1_buy_orders = []
    grind_1_distance_ratio = 0.0
    grind_2_sub_grind_count = 0
    grind_2_total_amount = 0.0
    grind_2_total_cost = 0.0
    grind_2_current_open_rate = 0.0
    grind_2_current_grind_stake = 0.0
    grind_2_current_grind_stake_profit = 0.0
    grind_2_is_sell_found = False
    grind_2_found = False
    grind_2_buy_orders = []
    grind_2_distance_ratio = 0.0
    grind_3_sub_grind_count = 0
    grind_3_total_amount = 0.0
    grind_3_total_cost = 0.0
    grind_3_current_open_rate = 0.0
    grind_3_current_grind_stake = 0.0
    grind_3_current_grind_stake_profit = 0.0
    grind_3_is_sell_found = False
    grind_3_found = False
    grind_3_buy_orders = []
    grind_3_distance_ratio = 0.0
    grind_4_sub_grind_count = 0
    grind_4_total_amount = 0.0
    grind_4_total_cost = 0.0
    grind_4_current_open_rate = 0.0
    grind_4_current_grind_stake = 0.0
    grind_4_current_grind_stake_profit = 0.0
    grind_4_is_sell_found = False
    grind_4_found = False
    grind_4_buy_orders = []
    grind_4_distance_ratio = 0.0
    grind_5_sub_grind_count = 0
    grind_5_total_amount = 0.0
    grind_5_total_cost = 0.0
    grind_5_current_open_rate = 0.0
    grind_5_current_grind_stake = 0.0
    grind_5_current_grind_stake_profit = 0.0
    grind_5_is_sell_found = False
    grind_5_found = False
    grind_5_buy_orders = []
    grind_5_distance_ratio = 0.0
    grind_6_sub_grind_count = 0
    grind_6_total_amount = 0.0
    grind_6_total_cost = 0.0
    grind_6_current_open_rate = 0.0
    grind_6_current_grind_stake = 0.0
    grind_6_current_grind_stake_profit = 0.0
    grind_6_is_sell_found = False
    grind_6_found = False
    grind_6_buy_orders = []
    grind_6_distance_ratio = 0.0
    grind_1_derisk_1_sub_grind_count = 0
    grind_1_derisk_1_total_amount = 0.0
    grind_1_derisk_1_total_cost = 0.0
    grind_1_derisk_1_current_open_rate = 0.0
    grind_1_derisk_1_current_grind_stake = 0.0
    grind_1_derisk_1_current_grind_stake_profit = 0.0
    grind_1_derisk_1_is_sell_found = False
    grind_1_derisk_1_found = False
    grind_1_derisk_1_buy_orders = []
    grind_1_derisk_1_distance_ratio = 0.0
    grind_2_derisk_1_sub_grind_count = 0
    grind_2_derisk_1_total_amount = 0.0
    grind_2_derisk_1_total_cost = 0.0
    grind_2_derisk_1_current_open_rate = 0.0
    grind_2_derisk_1_current_grind_stake = 0.0
    grind_2_derisk_1_current_grind_stake_profit = 0.0
    grind_2_derisk_1_is_sell_found = False
    grind_2_derisk_1_found = False
    grind_2_derisk_1_buy_orders = []
    grind_2_derisk_1_distance_ratio = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "sell") and (order is not filled_orders[0]):
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        if not is_derisk_1 and order_tag == "d1":
          derisk_1_sub_grind_count += 1
          derisk_1_total_amount += order.safe_filled
          derisk_1_total_cost += order.safe_filled * order.safe_price
          derisk_1_buy_orders.append(order.id)
          if not derisk_1_reentry_found and not is_derisk_1:
            derisk_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            derisk_1_reentry_found = True
            derisk_1_reentry_order = order
        elif not grind_1_derisk_1_is_sell_found and order_tag == "dl1":
          grind_1_derisk_1_sub_grind_count += 1
          grind_1_derisk_1_total_amount += order.safe_filled
          grind_1_derisk_1_total_cost += order.safe_filled * order.safe_price
          grind_1_derisk_1_buy_orders.append(order.id)
          if not grind_1_derisk_1_found:
            grind_1_derisk_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_1_derisk_1_found = True
        elif not grind_2_derisk_1_is_sell_found and order_tag == "dl2":
          grind_2_derisk_1_sub_grind_count += 1
          grind_2_derisk_1_total_amount += order.safe_filled
          grind_2_derisk_1_total_cost += order.safe_filled * order.safe_price
          grind_2_derisk_1_buy_orders.append(order.id)
          if not grind_2_derisk_1_found:
            grind_2_derisk_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_2_derisk_1_found = True
        elif not grind_6_is_sell_found and order_tag == "gd6":
          grind_6_sub_grind_count += 1
          grind_6_total_amount += order.safe_filled
          grind_6_total_cost += order.safe_filled * order.safe_price
          grind_6_buy_orders.append(order.id)
          if not grind_6_found:
            grind_6_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_6_found = True
        elif not grind_5_is_sell_found and order_tag == "gd5":
          grind_5_sub_grind_count += 1
          grind_5_total_amount += order.safe_filled
          grind_5_total_cost += order.safe_filled * order.safe_price
          grind_5_buy_orders.append(order.id)
          if not grind_5_found:
            grind_5_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_5_found = True
        elif not grind_4_is_sell_found and order_tag == "gd4":
          grind_4_sub_grind_count += 1
          grind_4_total_amount += order.safe_filled
          grind_4_total_cost += order.safe_filled * order.safe_price
          grind_4_buy_orders.append(order.id)
          if not grind_4_found:
            grind_4_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_4_found = True
        elif not grind_3_is_sell_found and order_tag == "gd3":
          grind_3_sub_grind_count += 1
          grind_3_total_amount += order.safe_filled
          grind_3_total_cost += order.safe_filled * order.safe_price
          grind_3_buy_orders.append(order.id)
          if not grind_3_found:
            grind_3_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_3_found = True
        elif not grind_2_is_sell_found and order_tag == "gd2":
          grind_2_sub_grind_count += 1
          grind_2_total_amount += order.safe_filled
          grind_2_total_cost += order.safe_filled * order.safe_price
          grind_2_buy_orders.append(order.id)
          if not grind_2_found:
            grind_2_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_2_found = True
        elif not grind_1_is_sell_found and order_tag not in [
          "r",
          "d1",
          "dl1",
          "dl2",
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "gm0",
          "gmd0",
        ]:
          grind_1_sub_grind_count += 1
          grind_1_total_amount += order.safe_filled
          grind_1_total_cost += order.safe_filled * order.safe_price
          grind_1_buy_orders.append(order.id)
          if not grind_1_found:
            grind_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_1_found = True
      elif order.ft_order_side == "buy":
        if (
          order is filled_exits[-1]
          and (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake
        ):
          partial_sell = True
          break
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            sell_order_tag = order.ft_order_tag
            order_mode = sell_order_tag.split(" ", 1)
            if len(order_mode) > 0:
              order_tag = order_mode[0]
        if order_tag in ["dl1", "ddl1"]:
          grind_1_derisk_1_is_sell_found = True
        elif order_tag in ["dl2", "ddl2"]:
          grind_2_derisk_1_is_sell_found = True
        elif order_tag in ["gd6", "dd6"]:
          grind_6_is_sell_found = True
        elif order_tag in ["gd5", "dd5"]:
          grind_5_is_sell_found = True
        if order_tag in ["gd4", "dd4"]:
          grind_4_is_sell_found = True
        elif order_tag in ["gd3", "dd3"]:
          grind_3_is_sell_found = True
        elif order_tag in ["gd2", "dd2"]:
          grind_2_is_sell_found = True
        elif order_tag in ["d1"]:
          if not is_derisk_1_found:
            is_derisk_1_found = True
            is_derisk_1 = True
            derisk_1_order = order
        elif order_tag in ["p", "r", "d", "dd0", "partial_exit", "force_exit", ""]:
          if order_tag in ["d"]:
            is_derisk_found = True
            is_derisk = True
          grind_1_is_sell_found = True
          grind_2_is_sell_found = True
          grind_3_is_sell_found = True
          grind_4_is_sell_found = True
          grind_5_is_sell_found = True
          grind_1_derisk_1_is_sell_found = True
          grind_2_derisk_1_is_sell_found = True
        elif order_tag not in [
          "dl1",
          "ddl1",
          "dl2",
          "ddl2",
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "dd2",
          "dd3",
          "dd4",
          "dd5",
          "dd6",
          "gm0",
          "gmd0",
        ]:
          grind_1_is_sell_found = True

    if derisk_1_sub_grind_count > 0:
      derisk_1_current_open_rate = derisk_1_total_cost / derisk_1_total_amount
      derisk_1_current_grind_stake = derisk_1_total_amount * exit_rate * (1 + trade.fee_close)
      derisk_1_current_grind_stake_profit = derisk_1_total_cost - derisk_1_current_grind_stake
    if grind_1_sub_grind_count > 0:
      grind_1_current_open_rate = grind_1_total_cost / grind_1_total_amount
      grind_1_current_grind_stake = grind_1_total_amount * exit_rate * (1 + trade.fee_close)
      grind_1_current_grind_stake_profit = grind_1_total_cost - grind_1_current_grind_stake
    if grind_2_sub_grind_count > 0:
      grind_2_current_open_rate = grind_2_total_cost / grind_2_total_amount
      grind_2_current_grind_stake = grind_2_total_amount * exit_rate * (1 + trade.fee_close)
      grind_2_current_grind_stake_profit = grind_2_total_cost - grind_2_current_grind_stake
    if grind_3_sub_grind_count > 0:
      grind_3_current_open_rate = grind_3_total_cost / grind_3_total_amount
      grind_3_current_grind_stake = grind_3_total_amount * exit_rate * (1 + trade.fee_close)
      grind_3_current_grind_stake_profit = grind_3_total_cost - grind_3_current_grind_stake
    if grind_4_sub_grind_count > 0:
      grind_4_current_open_rate = grind_4_total_cost / grind_4_total_amount
      grind_4_current_grind_stake = grind_4_total_amount * exit_rate * (1 + trade.fee_close)
      grind_4_current_grind_stake_profit = grind_4_total_cost - grind_4_current_grind_stake
    if grind_5_sub_grind_count > 0:
      grind_5_current_open_rate = grind_5_total_cost / grind_5_total_amount
      grind_5_current_grind_stake = grind_5_total_amount * exit_rate * (1 + trade.fee_close)
      grind_5_current_grind_stake_profit = grind_5_total_cost - grind_5_current_grind_stake
    if grind_6_sub_grind_count > 0:
      grind_6_current_open_rate = grind_6_total_cost / grind_6_total_amount
      grind_6_current_grind_stake = grind_6_total_amount * exit_rate * (1 + trade.fee_close)
      grind_6_current_grind_stake_profit = grind_6_total_cost - grind_6_current_grind_stake
    if grind_1_derisk_1_sub_grind_count > 0:
      grind_1_derisk_1_current_open_rate = grind_1_derisk_1_total_cost / grind_1_derisk_1_total_amount
      grind_1_derisk_1_current_grind_stake = grind_1_derisk_1_total_amount * exit_rate * (1 + trade.fee_close)
      grind_1_derisk_1_current_grind_stake_profit = grind_1_derisk_1_total_cost - grind_1_derisk_1_current_grind_stake
    if grind_2_derisk_1_sub_grind_count > 0:
      grind_2_derisk_1_current_open_rate = grind_2_derisk_1_total_cost / grind_2_derisk_1_total_amount
      grind_2_derisk_1_current_grind_stake = grind_2_derisk_1_total_amount * exit_rate * (1 + trade.fee_close)
      grind_2_derisk_1_current_grind_stake_profit = grind_2_derisk_1_total_cost - grind_2_derisk_1_current_grind_stake

    num_open_grinds = (
      grind_1_sub_grind_count
      + grind_2_sub_grind_count
      + grind_3_sub_grind_count
      + grind_4_sub_grind_count
      + grind_5_sub_grind_count
      + grind_6_sub_grind_count
      + grind_1_derisk_1_sub_grind_count
      + grind_2_derisk_1_sub_grind_count
    )

    # Sell remaining if partial fill on exit
    if partial_sell:
      order = filled_exits[-1]
      sell_amount = order.safe_remaining * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        self.dp.send_msg(
          f"Exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "p"
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    if is_grind_mode and (
      (filled_entries[0].safe_filled * (trade.stake_amount / trade.amount) - (min_stake * 1.5)) > min_stake
    ):
      is_first_entry_exit_found = False
      for order in filled_orders:
        if order.ft_order_side == "sell":
          order_tag = ""
          if has_order_tags:
            if order.ft_order_tag is not None:
              sell_order_tag = order.ft_order_tag
              order_mode = sell_order_tag.split(" ", 1)
              if len(order_mode) > 0:
                order_tag = order_mode[0]
          else:
            # no order tag support, assume the first exit is for the first buy
            is_first_entry_exit_found = True
          if order_tag in ["gm0", "gmd0"]:
            is_first_entry_exit_found = True
            break
      if not is_first_entry_exit_found:
        first_entry = filled_entries[0]
        first_entry_distance_ratio = -(exit_rate - first_entry.safe_price) / first_entry.safe_price
        # First entry exit
        if first_entry_distance_ratio > (
          (self.grind_mode_first_entry_profit_threshold_spot + fee_open_rate + fee_close_rate)
          if self.is_futures_mode
          else (self.grind_mode_first_entry_profit_threshold_spot + fee_open_rate + fee_close_rate)
        ):
          sell_amount = first_entry.safe_filled * exit_rate / trade.leverage
          if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
            sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
          ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
          if sell_amount > min_stake and ft_sell_amount > min_stake:
            grind_profit = -(exit_rate - first_entry.safe_price) / first_entry.safe_price
            coin_amount = sell_amount / exit_rate
            self.dp.send_msg(
              f"Grinding exit (gm0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            log.info(
              f"Grinding exit (gm0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            order_tag = "gm0"
            for grind_entry_id in grind_1_buy_orders:
              order_tag += " " + str(grind_entry_id)
            if has_order_tags:
              return -ft_sell_amount, order_tag
            else:
              return -ft_sell_amount
        # First entry de-risk
        if first_entry_distance_ratio < (
          self.grind_mode_first_entry_stop_threshold_spot
          if self.is_futures_mode
          else self.grind_mode_first_entry_stop_threshold_spot
        ):
          sell_amount = first_entry.safe_filled * exit_rate / trade.leverage
          if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
            sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
          ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
          if sell_amount > min_stake and ft_sell_amount > min_stake:
            grind_profit = -(exit_rate - first_entry.safe_price) / first_entry.safe_price
            coin_amount = sell_amount / exit_rate
            self.dp.send_msg(
              f"Grinding de-risk (gmd0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            log.info(
              f"Grinding de-risk (gmd0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {coin_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
            )
            order_tag = "gmd0"
            for grind_entry_id in grind_1_buy_orders:
              order_tag += " " + str(grind_entry_id)
            if has_order_tags:
              return -ft_sell_amount, order_tag
            else:
              return -ft_sell_amount

    is_short_grind_buy = self.short_grind_buy(last_candle, previous_candle, slice_profit)

    # Grinding derisk 1
    # Buy
    if (
      has_order_tags
      and is_derisk_1
      and not derisk_1_reentry_found
      and (not partial_sell)
      and (grind_1_derisk_1_sub_grind_count < grind_1_derisk_1_max_sub_grinds)
    ):
      if (
        (
          (
            (grind_1_derisk_1_sub_grind_count > 0)
            and -grind_1_derisk_1_distance_ratio < grind_1_derisk_1_sub_thresholds[grind_1_derisk_1_sub_grind_count]
          )
          or ((is_derisk or is_derisk_calc) and grind_1_derisk_1_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (last_candle["close"] < (last_candle["close_min_12"] * 1.06))
          and (last_candle["close"] < (last_candle["close_min_24"] * 1.08))
          and (last_candle["close"] < (last_candle["close_min_48"] * 1.10))
          and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.12))
          and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.14))
          and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.16))
          and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.18))
        )
        and (
          (last_candle["zlma_50_dec_15m"] == True)
          and (last_candle["zlma_50_dec_1h"] == True)
          and (last_candle["zlma_50_dec_4h"] == True)
          and (last_candle["EMA_200_dec_48_1h"] == True)
          and (last_candle["EMA_200_dec_24_4h"] == True)
        )
        and (
          is_short_grind_buy
          or (
            (last_candle["RSI_3"] < 84.0)
            and (last_candle["RSI_3_15m"] < 84.0)
            and (last_candle["RSI_3_1h"] < 70.0)
            and (last_candle["RSI_3_4h"] < 70.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] < last_candle["res_hlevel_4h"])
            and (last_candle["close"] > last_candle["sup_level_4h"])
          )
        )
      ):
        buy_amount = (
          slice_amount
          * grind_1_derisk_1_stakes[grind_1_derisk_1_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_1_derisk_1_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate
          grind_profit_stake = grind_1_derisk_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (dl1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (dl1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "dl1"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_1_derisk_1_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate
      if grind_profit > (grind_1_derisk_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_1_derisk_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (dl1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (dl1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "dl1"
          for grind_entry_id in grind_1_derisk_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (-grind_1_derisk_1_distance_ratio < grind_1_derisk_1_stop_grinds) and (is_derisk or is_derisk_calc):
      sell_amount = grind_1_derisk_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_1_derisk_1_current_open_rate > 0.0:
          grind_profit = (
            -((exit_rate - grind_1_derisk_1_current_open_rate) / grind_1_derisk_1_current_open_rate)
            if grind_1_derisk_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (ddl1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (ddl1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "ddl1"
        for grind_entry_id in grind_1_derisk_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding derisk 2
    # Buy
    if (
      has_order_tags
      and is_derisk_1
      and not derisk_1_reentry_found
      and (not partial_sell)
      and (grind_2_derisk_1_sub_grind_count < grind_2_derisk_1_max_sub_grinds)
    ):
      if (
        (
          (
            (grind_2_derisk_1_sub_grind_count > 0)
            and -grind_2_derisk_1_distance_ratio < grind_2_derisk_1_sub_thresholds[grind_2_derisk_1_sub_grind_count]
          )
          or ((is_derisk or is_derisk_calc) and grind_2_derisk_1_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (last_candle["close"] < (last_candle["close_min_12"] * 1.06))
          and (last_candle["close"] < (last_candle["close_min_24"] * 1.08))
          and (last_candle["close"] < (last_candle["close_min_48"] * 1.10))
          and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.12))
          and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.14))
        )
        and (
          (
            (grind_2_derisk_1_sub_grind_count == 0)
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 84.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 80.0)
                and (last_candle["RSI_3_4h"] < 80.0)
                and (last_candle["RSI_14"] > 64.0)
                # and (last_candle["zlma_50_dec_15m"] == True)
                and (last_candle["zlma_50_dec_1h"] == True)
                and (last_candle["zlma_50_dec_4h"] == True)
              )
            )
          )
          or (
            (grind_2_derisk_1_sub_grind_count > 0)
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 88.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 84.0)
                and (last_candle["RSI_3_4h"] < 84.0)
                and (last_candle["RSI_14"] > 54.0)
              )
            )
          )
        )
      ):
        buy_amount = (
          slice_amount
          * grind_2_derisk_1_stakes[grind_2_derisk_1_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_2_derisk_1_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate
          grind_profit_stake = grind_2_derisk_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (dl2) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (dl2) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "dl2"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_2_derisk_1_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate
      if grind_profit > (grind_2_derisk_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_2_derisk_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (dl2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (dl2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "dl2"
          for grind_entry_id in grind_2_derisk_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (grind_2_derisk_1_sub_grind_count > 0)
      and (
        (-(exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate)
        < grind_2_derisk_1_stop_grinds
      )
      and (is_derisk or is_derisk_calc)
    ):
      sell_amount = grind_2_derisk_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_2_derisk_1_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_2_derisk_1_current_open_rate) / grind_2_derisk_1_current_open_rate)
            if grind_2_derisk_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (ddl2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (ddl2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_derisk_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "ddl2"
        for grind_entry_id in grind_2_derisk_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 1
    # Buy
    if (not partial_sell) and (grind_1_sub_grind_count < grind_1_max_sub_grinds):
      if (
        (
          ((grind_1_sub_grind_count > 0) and -grind_1_distance_ratio < grind_1_sub_thresholds[grind_1_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_1_sub_grind_count == 0)
          or (is_grind_mode and grind_1_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
            )
            and (
              (
                (grind_1_sub_grind_count == 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["RSI_14"] > 64.0)
                    # and (last_candle["zlma_50_dec_15m"] == True)
                    # and (last_candle["zlma_50_dec_1h"] == False)
                    # and (last_candle["zlma_50_dec_4h"] == False)
                    and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
                  )
                  or (
                    (last_candle["RSI_14"] > 64.0)
                    and (previous_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["close"] > (last_candle["SMA_16"] * 1.012))
                  )
                )
              )
              or (
                (grind_1_sub_grind_count > 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 88.0)
                    and (last_candle["RSI_3_15m"] < 88.0)
                    # and (last_candle["RSI_3_1h"] < 88.0)
                    # and (last_candle["RSI_3_4h"] < 88.0)
                    and (last_candle["RSI_14"] > 58.0)
                  )
                )
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_1_stakes[grind_1_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_1_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
          grind_profit_stake = grind_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd1"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    if (
      self.is_futures_mode
      and has_order_tags
      and (not partial_sell)
      and slice_profit > (0.65 / trade.leverage)
      and (is_derisk or is_derisk_calc or is_grind_mode)
      and (grind_1_sub_grind_count < grind_1_max_sub_grinds)
    ):
      buy_amount = (
        slice_amount * grind_1_stakes[grind_1_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
      )
      if buy_amount < (min_stake * 1.5):
        buy_amount = min_stake * 1.5
      if buy_amount > max_stake:
        return None
      grind_profit = 0.0
      grind_profit_stake = 0.0
      if grind_1_sub_grind_count > 0:
        grind_profit = -(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
        grind_profit_stake = grind_1_current_grind_stake_profit
      self.dp.send_msg(
        f"Grinding entry (gd1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      log.info(
        f"Grinding entry (gd1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      order_tag = "gd1"
      if has_order_tags:
        return buy_amount, order_tag
      else:
        return buy_amount

    # Sell
    if grind_1_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
      if grind_profit > (grind_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd1"
          for grind_entry_id in grind_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_1_sub_grind_count > 0)
        and ((-(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate) < grind_1_stop_grinds)
        # (
        #   grind_1_current_grind_stake_profit
        #   < (slice_amount * grind_1_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
        # )
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 14) or is_backtest)
    ):
      sell_amount = grind_1_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_1_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate)
            if grind_1_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd1"
        for grind_entry_id in grind_1_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 2
    # Buy
    if has_order_tags and (not partial_sell) and (grind_2_sub_grind_count < grind_2_max_sub_grinds):
      if (
        (
          ((grind_2_sub_grind_count > 0) and -grind_2_distance_ratio < grind_2_sub_thresholds[grind_2_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_2_sub_grind_count == 0)
          or (is_grind_mode and grind_2_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
            )
            and (
              (
                (grind_2_sub_grind_count == 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["RSI_14"] > 64.0)
                    # and (last_candle["zlma_50_dec_15m"] == True)
                    # and (last_candle["zlma_50_dec_1h"] == False)
                    # and (last_candle["zlma_50_dec_4h"] == False)
                    and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
                  )
                  or (
                    (last_candle["RSI_14"] > 64.0)
                    and (previous_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["close"] > (last_candle["SMA_16"] * 1.012))
                  )
                )
              )
              or (
                (grind_2_sub_grind_count > 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 88.0)
                    and (last_candle["RSI_3_15m"] < 88.0)
                    # and (last_candle["RSI_3_1h"] < 88.0)
                    # and (last_candle["RSI_3_4h"] < 88.0)
                    and (last_candle["RSI_14"] > 58.0)
                  )
                )
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_2_stakes[grind_2_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_2_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
          grind_profit_stake = grind_2_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd2) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd2) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd2"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_2_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
      if grind_profit > (grind_2_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_2_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd2"
          for grind_entry_id in grind_2_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_2_sub_grind_count > 0)
        and ((-(exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate) < grind_2_stop_grinds)
        # (
        #   grind_2_current_grind_stake_profit
        #   < (slice_amount * grind_2_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
        # )
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 14) or is_backtest)
    ):
      sell_amount = grind_2_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_2_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate)
            if grind_2_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd2"
        for grind_entry_id in grind_2_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 3
    # Buy
    if has_order_tags and (not partial_sell) and (grind_3_sub_grind_count < grind_3_max_sub_grinds):
      if (
        (
          ((grind_3_sub_grind_count > 0) and -grind_3_distance_ratio < grind_3_sub_thresholds[grind_3_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_3_sub_grind_count == 0)
          or (is_grind_mode and grind_3_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
            )
            and (
              (
                (grind_3_sub_grind_count == 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["RSI_14"] > 64.0)
                    # and (last_candle["zlma_50_dec_15m"] == True)
                    # and (last_candle["zlma_50_dec_1h"] == False)
                    # and (last_candle["zlma_50_dec_4h"] == False)
                    and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
                  )
                  or (
                    (last_candle["RSI_14"] > 64.0)
                    and (previous_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["close"] > (last_candle["SMA_16"] * 1.012))
                  )
                )
              )
              or (
                (grind_3_sub_grind_count > 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 88.0)
                    and (last_candle["RSI_3_15m"] < 88.0)
                    # and (last_candle["RSI_3_1h"] < 88.0)
                    # and (last_candle["RSI_3_4h"] < 88.0)
                    and (last_candle["RSI_14"] > 58.0)
                  )
                )
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_3_stakes[grind_3_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_3_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
          grind_profit_stake = grind_3_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd3) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd3) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd3"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_3_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
      if grind_profit > (grind_3_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_3_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd3"
          for grind_entry_id in grind_3_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_3_sub_grind_count > 0)
        and ((-(exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate) < grind_3_stop_grinds)
        # (
        #   grind_3_current_grind_stake_profit
        #   < (slice_amount * grind_3_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
        # )
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 14) or is_backtest)
    ):
      sell_amount = grind_3_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_3_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate)
            if grind_3_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd3"
        for grind_entry_id in grind_3_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 4
    # Buy
    if has_order_tags and (not partial_sell) and (grind_4_sub_grind_count < grind_4_max_sub_grinds):
      if (
        (
          ((grind_4_sub_grind_count > 0) and -grind_4_distance_ratio < grind_4_sub_thresholds[grind_4_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_4_sub_grind_count == 0)
          or (is_grind_mode and grind_4_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
            )
            and (
              (
                (grind_4_sub_grind_count == 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["RSI_14"] > 64.0)
                    # and (last_candle["zlma_50_dec_15m"] == True)
                    # and (last_candle["zlma_50_dec_1h"] == False)
                    # and (last_candle["zlma_50_dec_4h"] == False)
                    and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
                  )
                  or (
                    (last_candle["RSI_14"] > 64.0)
                    and (previous_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["close"] > (last_candle["SMA_16"] * 1.012))
                  )
                )
              )
              or (
                (grind_4_sub_grind_count > 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 88.0)
                    and (last_candle["RSI_3_15m"] < 88.0)
                    # and (last_candle["RSI_3_1h"] < 88.0)
                    # and (last_candle["RSI_3_4h"] < 88.0)
                    and (last_candle["RSI_14"] > 58.0)
                  )
                )
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_4_stakes[grind_4_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_4_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
          grind_profit_stake = grind_4_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd4) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd4) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd4"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_4_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
      if grind_profit > (grind_4_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_4_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd4"
          for grind_entry_id in grind_4_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_4_sub_grind_count > 0)
        and ((-(exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate) < grind_4_stop_grinds)
        # (
        #   grind_4_current_grind_stake_profit
        #   < (slice_amount * grind_4_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
        # )
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 14) or is_backtest)
    ):
      sell_amount = grind_4_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_4_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate)
            if grind_4_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd4"
        for grind_entry_id in grind_4_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 5
    # Buy
    if has_order_tags and (not partial_sell) and (grind_5_sub_grind_count < grind_5_max_sub_grinds):
      if (
        (
          ((grind_5_sub_grind_count > 0) and -grind_5_distance_ratio < grind_5_sub_thresholds[grind_5_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_5_sub_grind_count == 0)
          or (is_grind_mode and grind_5_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
            )
            and (
              (
                (grind_5_sub_grind_count == 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["RSI_14"] > 64.0)
                    # and (last_candle["zlma_50_dec_15m"] == True)
                    # and (last_candle["zlma_50_dec_1h"] == False)
                    # and (last_candle["zlma_50_dec_4h"] == False)
                    and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
                  )
                  or (
                    (last_candle["RSI_14"] > 64.0)
                    and (previous_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["close"] > (last_candle["SMA_16"] * 1.012))
                  )
                )
              )
              or (
                (grind_5_sub_grind_count > 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 88.0)
                    and (last_candle["RSI_3_15m"] < 88.0)
                    # and (last_candle["RSI_3_1h"] < 88.0)
                    # and (last_candle["RSI_3_4h"] < 88.0)
                    and (last_candle["RSI_14"] > 58.0)
                  )
                )
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_5_stakes[grind_5_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_5_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
          grind_profit_stake = grind_5_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd5) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd5) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd5"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_5_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
      if grind_profit > (grind_5_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_5_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd5"
          for grind_entry_id in grind_5_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_5_sub_grind_count > 0)
        and ((-(exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate) < grind_5_stop_grinds)
        # (
        #   grind_5_current_grind_stake_profit
        #   < (slice_amount * grind_5_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
        # )
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 14) or is_backtest)
    ):
      sell_amount = grind_5_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_5_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate)
            if grind_5_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd5"
        for grind_entry_id in grind_5_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # Grinding 6
    # Buy
    if has_order_tags and (not partial_sell) and (grind_6_sub_grind_count < grind_6_max_sub_grinds):
      if (
        (
          ((grind_6_sub_grind_count > 0) and -grind_6_distance_ratio < grind_6_sub_thresholds[grind_6_sub_grind_count])
          or ((is_derisk or is_derisk_calc) and grind_6_sub_grind_count == 0)
          or (is_grind_mode and grind_6_sub_grind_count == 0)
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
            )
            and (
              (
                (grind_6_sub_grind_count == 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["RSI_14"] > 64.0)
                    # and (last_candle["zlma_50_dec_15m"] == True)
                    # and (last_candle["zlma_50_dec_1h"] == False)
                    # and (last_candle["zlma_50_dec_4h"] == False)
                    and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
                  )
                  or (
                    (last_candle["RSI_14"] > 64.0)
                    and (previous_candle["RSI_3"] < 90.0)
                    and (last_candle["RSI_3_15m"] < 90.0)
                    and (last_candle["RSI_3_1h"] < 90.0)
                    and (last_candle["RSI_3_4h"] < 90.0)
                    and (last_candle["close"] > (last_candle["SMA_16"] * 1.012))
                  )
                )
              )
              or (
                (grind_6_sub_grind_count > 0)
                and (
                  is_short_grind_buy
                  or (
                    (last_candle["RSI_3"] < 88.0)
                    and (last_candle["RSI_3_15m"] < 88.0)
                    # and (last_candle["RSI_3_1h"] < 88.0)
                    # and (last_candle["RSI_3_4h"] < 88.0)
                    and (last_candle["RSI_14"] > 58.0)
                  )
                )
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 58.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.006))
          )
        )
      ):
        buy_amount = (
          slice_amount * grind_6_stakes[grind_6_sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_6_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate
          grind_profit_stake = grind_6_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (gd6) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_6_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (gd6) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_6_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "gd6"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # Sell
    if grind_6_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate
      if grind_profit > (grind_6_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_6_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (gd6) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (gd6) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "gd6"
          for grind_entry_id in grind_6_buy_orders:
            order_tag += " " + str(grind_entry_id)
          if has_order_tags:
            return -ft_sell_amount, order_tag
          else:
            return -ft_sell_amount

    # Grind stop
    if (
      (
        (grind_6_sub_grind_count > 0)
        and ((-(exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate) < grind_6_stop_grinds)
        # (
        #   grind_6_current_grind_stake_profit
        #   < (slice_amount * grind_6_stop_grinds / (trade.leverage if self.is_futures_mode else 1.0))
        # )
        and (is_derisk or is_derisk_calc or is_grind_mode)
      )
      # temporary
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 14) or is_backtest)
    ):
      sell_amount = grind_6_total_amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        if grind_6_current_open_rate > 0.0:
          grind_profit = (
            (-(exit_rate - grind_6_current_open_rate) / grind_6_current_open_rate)
            if grind_6_is_sell_found
            else profit_ratio
          )
        self.dp.send_msg(
          f"Grinding stop exit (dd6) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        log.info(
          f"Grinding stop exit (dd6) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_6_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}%"
        )
        order_tag = "dd6"
        for grind_entry_id in grind_6_buy_orders:
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    # De-risk 1 reentry
    if (
      is_derisk_1
      and not derisk_1_reentry_found
      and derisk_1_order is not None
      and (
        (-(current_rate - derisk_1_order.safe_price) / derisk_1_order.safe_price)
        < (
          self.regular_mode_derisk_1_reentry_futures
          if self.is_futures_mode
          else self.regular_mode_derisk_1_reentry_spot
        )
      )
    ):
      if (
        (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (last_candle["close"] < (last_candle["close_min_12"] * 1.06))
          and (last_candle["close"] < (last_candle["close_min_24"] * 1.08))
          and (last_candle["close"] < (last_candle["close_min_48"] * 1.10))
          and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.12))
          and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.14))
          and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.16))
          and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.18))
        )
        and (
          (last_candle["zlma_50_dec_15m"] == True)
          and (last_candle["zlma_50_dec_1h"] == True)
          and (last_candle["zlma_50_dec_4h"] == True)
          and (last_candle["EMA_200_dec_48_1h"] == True)
          and (last_candle["EMA_200_dec_24_4h"] == True)
          and (last_candle["close"] < last_candle["res_hlevel_4h"])
          and (last_candle["close"] > last_candle["sup_level_4h"])
        )
        and (
          is_short_grind_buy
          or (
            (last_candle["RSI_3"] < 70.0)
            and (last_candle["RSI_3_15m"] < 70.0)
            and (last_candle["RSI_3_1h"] < 70.0)
            and (last_candle["RSI_3_4h"] < 70.0)
            and (last_candle["RSI_14"] > 58.0)
          )
        )
      ):
        buy_amount = derisk_1_order.safe_filled * derisk_1_order.safe_price
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if derisk_1_sub_grind_count > 0:
          grind_profit = -(exit_rate - derisk_1_current_open_rate) / derisk_1_current_open_rate
          grind_profit_stake = derisk_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Re-entry (d1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Re-entry (d1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({derisk_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "d1"
        if has_order_tags:
          return buy_amount, order_tag
        else:
          return buy_amount

    # De-risk level 1
    if (
      has_order_tags
      # and not is_derisk_1
      and derisk_1_reentry_found
      and derisk_1_reentry_order is not None
      # and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 5) or is_backtest)
      and -derisk_1_distance_ratio
      < (
        (self.regular_mode_derisk_1_futures if self.is_futures_mode else self.regular_mode_derisk_1_spot)
        / (trade.leverage if self.is_futures_mode else 1.0)
      )
    ):
      sell_amount = derisk_1_reentry_order.safe_filled * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk (d1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk (d1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d1"

    # De-risk
    if (
      not is_derisk_found
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 2, 5) or is_backtest)
      and profit_stake
      < (
        slice_amount
        * (
          (self.regular_mode_derisk_futures if self.is_futures_mode else self.regular_mode_derisk_spot)
          if (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 5) or is_backtest)
          else (self.regular_mode_derisk_futures_old if self.is_futures_mode else self.regular_mode_derisk_spot_old)
        )
        # / (trade.leverage if self.is_futures_mode else 1.0)
      )
    ):
      sell_amount = trade.amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d", is_derisk

    # De-risk
    if (
      (
        (profit_stake < (slice_amount * grind_derisk / (trade.leverage if self.is_futures_mode else 1.0)))
        and (
          (
            (trade.amount * exit_rate / (trade.leverage if self.is_futures_mode else 1.0))
            - (
              (
                derisk_1_total_amount
                + grind_1_derisk_1_total_amount
                + grind_2_derisk_1_total_amount
                + grind_1_total_amount
                + grind_2_total_amount
                + grind_3_total_amount
                + grind_4_total_amount
                + grind_5_total_amount
                + grind_6_total_amount
              )
              * exit_rate
              # / (trade.leverage if self.is_futures_mode else 1.0)
            )
          )
          > (min_stake * 3.0)
        )
        # temporary
        and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 12, 19) or is_backtest)
      )
      # temporary
      and (
        (trade.open_date_utc.replace(tzinfo=None) >= datetime(2023, 8, 28) or is_backtest)
        or (filled_entries[-1].order_date_utc.replace(tzinfo=None) >= datetime(2023, 8, 28) or is_backtest)
      )
    ):
      sell_amount = trade.amount * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        self.dp.send_msg(
          f"De-risk (dd0) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk (dd0) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "dd0"
        for grind_entry_id in (
          grind_1_buy_orders
          + grind_2_buy_orders
          + grind_3_buy_orders
          + grind_4_buy_orders
          + grind_5_buy_orders
          + grind_6_buy_orders
          + grind_1_derisk_1_buy_orders
          + grind_2_derisk_1_buy_orders
        ):
          order_tag += " " + str(grind_entry_id)
        if has_order_tags:
          return -ft_sell_amount, order_tag
        else:
          return -ft_sell_amount

    return None

  # Short Grinding Buy
  # ---------------------------------------------------------------------------------------------
  def short_grind_buy(self, last_candle: Series, previous_candle: Series, slice_profit: float) -> float:
    if (
      (last_candle["protections_short_global"] == True)
      and (last_candle["protections_short_rebuy"] == True)
      and (last_candle["global_protections_short_pump"] == True)
      and (last_candle["global_protections_short_dump"] == True)
      and (
        (last_candle["close"] < (last_candle["close_min_12"] * 1.12))
        and (last_candle["close"] < (last_candle["close_min_24"] * 1.18))
        and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
        and (last_candle["btc_pct_close_min_72_5m"] < -0.03)
        and (last_candle["btc_pct_close_min_24_5m"] < -0.03)
      )
      and (
        (last_candle["enter_short"] == True)
        or (
          (last_candle["RSI_3"] < 90.0)
          and (last_candle["RSI_3_15m"] < 80.0)
          and (last_candle["RSI_3_1h"] < 80.0)
          and (last_candle["RSI_3_4h"] < 80.0)
          and (last_candle["RSI_14"] > 56.0)
          and (last_candle["ha_close"] < last_candle["ha_open"])
          and (last_candle["EMA_12"] > (last_candle["EMA_26"] * 1.010))
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["RSI_14_1h"] < 80.0)
        )
        or (
          (last_candle["RSI_14"] > 64.0)
          and (last_candle["close"] > (last_candle["SMA_16"] * 1.006))
          and (last_candle["RSI_3"] < 86.0)
          and (last_candle["RSI_3_15m"] < 70.0)
          and (last_candle["RSI_3_1h"] < 70.0)
          and (last_candle["RSI_3_4h"] < 70.0)
          and (last_candle["zlma_50_dec_1h"] == True)
        )
        or (
          (last_candle["RSI_14"] > 64.0)
          and (previous_candle["RSI_3"] < 94.0)
          and (last_candle["EMA_26"] < last_candle["EMA_12"])
          and ((last_candle["EMA_26"] - last_candle["EMA_12"]) > (last_candle["open"] * 0.010))
          and ((previous_candle["EMA_26"] - previous_candle["EMA_12"]) > (last_candle["open"] / 100.0))
          and (last_candle["RSI_3_1h"] < 80.0)
          and (last_candle["RSI_3_4h"] < 80.0)
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["RSI_14_1h"] > 20.0)
        )
        or (
          (last_candle["RSI_14"] < 70.0)
          and (last_candle["RSI_14"] > 40.0)
          and (last_candle["hma_70_buy"] == False)
          and (last_candle["close"] < (last_candle["low_min_12_1h"] * 0.90))
          and (last_candle["CTI_20_15m"] > -0.50)
          and (last_candle["RSI_14_15m"] > 50.0)
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["RSI_14_1h"] > 20.0)
          and (last_candle["zlma_50_dec_1h"] == True)
          and (last_candle["zlma_50_dec_4h"] == True)
        )
        or (
          (last_candle["RSI_3"] < 88.0)
          and (last_candle["RSI_3_15m"] < 80.0)
          and (last_candle["RSI_3_1h"] < 80.0)
          and (last_candle["RSI_3_4h"] < 80.0)
          and (last_candle["RSI_14"] > 64.0)
          and (last_candle["zlma_50_dec_15m"] == True)
          and (last_candle["zlma_50_dec_1h"] == True)
        )
        or (
          (last_candle["RSI_14"] > 60.0)
          and (last_candle["RSI_14_15m"] > 60.0)
          and (last_candle["RSI_3"] < 94.0)
          and (last_candle["EMA_26_15m"] < last_candle["EMA_12_15m"])
          and ((last_candle["EMA_12_15m"] - last_candle["EMA_26_15m"]) > (last_candle["open_15m"] * 0.006))
          and ((previous_candle["EMA_12_15m"] - previous_candle["EMA_26_15m"]) > (last_candle["open_15m"] / 100.0))
          and (last_candle["RSI_3_15m"] < 90.0)
          and (last_candle["RSI_3_1h"] < 74.0)
          and (last_candle["RSI_3_4h"] < 74.0)
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["RSI_14_1h"] > 20.0)
        )
        or (
          (last_candle["RSI_14"] < 65.0)
          and (last_candle["RSI_3"] < 96.0)
          and (last_candle["RSI_3"] > 54.0)
          and (last_candle["RSI_14"] > previous_candle["RSI_14"])
          and (last_candle["close"] > (last_candle["SMA_16"] * 1.018))
          and (last_candle["CTI_20"] > 0.60)
          and (last_candle["RSI_3_1h"] < 80.0)
          and (last_candle["RSI_3_4h"] < 80.0)
          and (last_candle["not_downtrend_1d"] == False)
          and (last_candle["zlma_50_dec_1h"] == True)
        )
        or (
          (last_candle["RSI_3"] < 88.0)
          and (last_candle["RSI_3_15m"] < 74.0)
          and (last_candle["RSI_3_1h"] < 74.0)
          and (last_candle["RSI_3_4h"] < 74.0)
          and (last_candle["RSI_14"] > 60.0)
          and (last_candle["EMA_12"] > (last_candle["EMA_26"] * 1.006))
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["RSI_14_1h"] > 20.0)
          and (last_candle["CTI_20_4h"] > -0.80)
          and (last_candle["RSI_14_4h"] > 20.0)
          and (last_candle["EMA_200_dec_48_1h"] == True)
        )
        or (
          (last_candle["RSI_14"] > 40.0)
          and (last_candle["hma_55_buy"] == False)
          and (last_candle["RSI_3_1h"] < 96.0)
          and (last_candle["RSI_3_4h"] < 96.0)
          and (last_candle["CTI_20_15m"] > -0.80)
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["CTI_20_4h"] > -0.80)
          and (last_candle["RSI_14_1h"] > 20.0)
          and (last_candle["close"] > (last_candle["low_min_12_1h"] * 1.10))
          and (last_candle["zlma_50_dec_1h"] == True)
          and (last_candle["zlma_50_dec_4h"] == True)
        )
        or (
          (last_candle["RSI_3"] < 88.0)
          and (last_candle["RSI_3_15m"] < 70.0)
          and (last_candle["RSI_3_1h"] < 70.0)
          and (last_candle["RSI_3_4h"] < 70.0)
          and (last_candle["RSI_14"] > 60.0)
          and (last_candle["CTI_20_15m"] > -0.80)
          and (last_candle["RSI_14_15m"] > 30.0)
          and (last_candle["CTI_20_1h"] > -0.80)
          and (last_candle["RSI_14_1h"] > 20.0)
          and (last_candle["CTI_20_4h"] > -0.80)
          and (last_candle["RSI_14_4h"] > 20.0)
          and (last_candle["WILLR_14_1h"] < -20.0)
          and (last_candle["EMA_12"] > (last_candle["EMA_26"] * 1.005))
          and (last_candle["zlma_50_dec_1h"] == True)
        )
        or (
          (last_candle["RSI_3"] < 88.0)
          and (last_candle["RSI_3_15m"] < 70.0)
          and (last_candle["RSI_3_1h"] < 70.0)
          and (last_candle["RSI_3_4h"] < 70.0)
          and (last_candle["RSI_14"] > 60.0)
          and (last_candle["RSI_14_1d"] > 30.0)
          and (last_candle["close"] > last_candle["sup_level_1h"])
          and (last_candle["close"] > last_candle["sup_level_4h"])
          and (last_candle["close"] > last_candle["sup_level_1d"])
          and (last_candle["not_downtrend_1h"] == False)
          and (last_candle["not_downtrend_4h"] == False)
          and (last_candle["not_downtrend_1d"] == False)
        )
        or (
          (last_candle["RSI_3"] < 88.0)
          and (last_candle["RSI_3_15m"] < 70.0)
          and (last_candle["RSI_3_1h"] < 70.0)
          and (last_candle["RSI_3_4h"] < 70.0)
          and (last_candle["RSI_14"] > 60.0)
          and (last_candle["ha_close"] < last_candle["ha_open"])
          and (last_candle["close"] < last_candle["res_hlevel_4h"])
          and (last_candle["close"] > last_candle["sup_level_4h"])
          and (last_candle["close"] < last_candle["res_hlevel_1d"])
          and (last_candle["close"] > last_candle["sup_level_1d"])
          and (last_candle["close"] > last_candle["sup3_1d"])
          and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.15))
          and (last_candle["hl_pct_change_24_1h"] > -0.35)
        )
        or (
          (last_candle["RSI_3"] < 88.0)
          and (last_candle["RSI_3_15m"] < 70.0)
          and (last_candle["RSI_3_1h"] < 70.0)
          and (last_candle["RSI_3_4h"] < 70.0)
          and (last_candle["RSI_14"] > 54.0)
          and (previous_candle["chandelier_dir"] > 0)
          and (last_candle["chandelier_dir"] < -0)
          and (last_candle["close"] < last_candle["res_hlevel_4h"])
          and (last_candle["close"] > last_candle["sup_level_4h"])
          and (last_candle["close"] < last_candle["res_hlevel_1d"])
          and (last_candle["close"] > last_candle["sup_level_1d"])
        )
      )
    ):
      return True

    return False

  # Short Grinding Adjust Trade Position No De-Risk
  # ---------------------------------------------------------------------------------------------
  def short_adjust_trade_position_no_derisk(
    self,
    trade: Trade,
    enter_tags,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    last_candle: Series,
    previous_candle: Series,
    filled_orders: "Orders",
    filled_entries: "Orders",
    filled_exits: "Orders",
    exit_rate: float,
    slice_amount: float,
    slice_profit_entry: float,
    slice_profit: float,
    profit_ratio: float,
    profit_stake: float,
    profit_init_ratio: float,
    current_stake_amount: float,
    has_order_tags: bool,
    **kwargs,
  ) -> tuple[Optional[float], str, bool]:
    is_backtest = self.dp.runmode.value in ["backtest", "hyperopt"]

    max_rebuy_sub_grinds = 0
    regular_mode_rebuy_stakes = (
      self.regular_mode_rebuy_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_rebuy_stakes_spot.copy()
    )
    regular_mode_rebuy_sub_thresholds = (
      self.regular_mode_rebuy_thresholds_futures if self.is_futures_mode else self.regular_mode_rebuy_thresholds_spot
    )
    if (slice_amount * regular_mode_rebuy_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_rebuy_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_rebuy_stakes):
        regular_mode_rebuy_stakes[i] *= multi
    max_rebuy_sub_grinds = len(regular_mode_rebuy_stakes)

    max_grind_1_sub_grinds = 0
    regular_mode_grind_1_stakes = (
      self.regular_mode_grind_1_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_1_stakes_spot.copy()
    )
    regular_mode_grind_1_sub_thresholds = (
      self.regular_mode_grind_1_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_1_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_1_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_1_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_1_stakes):
        regular_mode_grind_1_stakes[i] *= multi
    max_grind_1_sub_grinds = len(regular_mode_grind_1_stakes)
    regular_mode_grind_1_stop_grinds = (
      self.regular_mode_grind_1_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_1_stop_grinds_spot
    )
    regular_mode_grind_1_profit_threshold = (
      self.regular_mode_grind_1_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_1_profit_threshold_spot
    )

    max_grind_2_sub_grinds = 0
    regular_mode_grind_2_stakes = (
      self.regular_mode_grind_2_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_2_stakes_spot.copy()
    )
    regular_mode_grind_2_sub_thresholds = (
      self.regular_mode_grind_2_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_2_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_2_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_2_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_2_stakes):
        regular_mode_grind_2_stakes[i] *= multi
    max_grind_2_sub_grinds = len(regular_mode_grind_2_stakes)
    regular_mode_grind_2_stop_grinds = (
      self.regular_mode_grind_2_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_2_stop_grinds_spot
    )
    regular_mode_grind_2_profit_threshold = (
      self.regular_mode_grind_2_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_2_profit_threshold_spot
    )

    max_grind_3_sub_grinds = 0
    regular_mode_grind_3_stakes = (
      self.regular_mode_grind_3_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_3_stakes_spot.copy()
    )
    regular_mode_grind_3_sub_thresholds = (
      self.regular_mode_grind_3_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_3_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_3_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_3_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_3_stakes):
        regular_mode_grind_3_stakes[i] *= multi
    max_grind_3_sub_grinds = len(regular_mode_grind_3_stakes)
    regular_mode_grind_3_stop_grinds = (
      self.regular_mode_grind_3_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_3_stop_grinds_spot
    )
    regular_mode_grind_3_profit_threshold = (
      self.regular_mode_grind_3_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_3_profit_threshold_spot
    )

    max_grind_4_sub_grinds = 0
    regular_mode_grind_4_stakes = (
      self.regular_mode_grind_4_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_4_stakes_spot.copy()
    )
    regular_mode_grind_4_sub_thresholds = (
      self.regular_mode_grind_4_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_4_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_4_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_4_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_4_stakes):
        regular_mode_grind_4_stakes[i] *= multi
    max_grind_4_sub_grinds = len(regular_mode_grind_4_stakes)
    regular_mode_grind_4_stop_grinds = (
      self.regular_mode_grind_4_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_4_stop_grinds_spot
    )
    regular_mode_grind_4_profit_threshold = (
      self.regular_mode_grind_4_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_4_profit_threshold_spot
    )

    max_grind_5_sub_grinds = 0
    regular_mode_grind_5_stakes = (
      self.regular_mode_grind_5_stakes_futures.copy()
      if self.is_futures_mode
      else self.regular_mode_grind_5_stakes_spot.copy()
    )
    regular_mode_grind_5_sub_thresholds = (
      self.regular_mode_grind_5_thresholds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_5_thresholds_spot
    )
    if (slice_amount * regular_mode_grind_5_stakes[0] / trade.leverage) < min_stake:
      multi = min_stake / slice_amount / regular_mode_grind_5_stakes[0] * trade.leverage
      for i, _ in enumerate(regular_mode_grind_5_stakes):
        regular_mode_grind_5_stakes[i] *= multi
    max_grind_5_sub_grinds = len(regular_mode_grind_5_stakes)
    regular_mode_grind_5_stop_grinds = (
      self.regular_mode_grind_5_stop_grinds_futures
      if self.is_futures_mode
      else self.regular_mode_grind_5_stop_grinds_spot
    )
    regular_mode_grind_5_profit_threshold = (
      self.regular_mode_grind_5_profit_threshold_futures
      if self.is_futures_mode
      else self.regular_mode_grind_5_profit_threshold_spot
    )

    partial_sell = False
    is_derisk = False
    is_derisk_1 = False
    rebuy_sub_grind_count = 0
    rebuy_total_amount = 0.0
    rebuy_total_cost = 0.0
    rebuy_current_open_rate = 0.0
    rebuy_current_grind_stake = 0.0
    rebuy_current_grind_stake_profit = 0.0
    rebuy_is_sell_found = False
    rebuy_found = False
    rebuy_buy_orders = []
    rebuy_distance_ratio = 0.0
    grind_1_sub_grind_count = 0
    grind_1_total_amount = 0.0
    grind_1_total_cost = 0.0
    grind_1_current_open_rate = 0.0
    grind_1_current_grind_stake = 0.0
    grind_1_current_grind_stake_profit = 0.0
    grind_1_is_sell_found = False
    grind_1_found = False
    grind_1_buy_orders = []
    grind_1_distance_ratio = 0.0
    grind_2_sub_grind_count = 0
    grind_2_total_amount = 0.0
    grind_2_total_cost = 0.0
    grind_2_current_open_rate = 0.0
    grind_2_current_grind_stake = 0.0
    grind_2_current_grind_stake_profit = 0.0
    grind_2_is_sell_found = False
    grind_2_found = False
    grind_2_buy_orders = []
    grind_2_distance_ratio = 0.0
    grind_3_sub_grind_count = 0
    grind_3_total_amount = 0.0
    grind_3_total_cost = 0.0
    grind_3_current_open_rate = 0.0
    grind_3_current_grind_stake = 0.0
    grind_3_current_grind_stake_profit = 0.0
    grind_3_is_sell_found = False
    grind_3_found = False
    grind_3_buy_orders = []
    grind_3_distance_ratio = 0.0
    grind_4_sub_grind_count = 0
    grind_4_total_amount = 0.0
    grind_4_total_cost = 0.0
    grind_4_current_open_rate = 0.0
    grind_4_current_grind_stake = 0.0
    grind_4_current_grind_stake_profit = 0.0
    grind_4_is_sell_found = False
    grind_4_found = False
    grind_4_buy_orders = []
    grind_4_distance_ratio = 0.0
    grind_5_sub_grind_count = 0
    grind_5_total_amount = 0.0
    grind_5_total_cost = 0.0
    grind_5_current_open_rate = 0.0
    grind_5_current_grind_stake = 0.0
    grind_5_current_grind_stake_profit = 0.0
    grind_5_is_sell_found = False
    grind_5_found = False
    grind_5_buy_orders = []
    grind_5_distance_ratio = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "sell") and (order is not filled_orders[0]):
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        if not grind_1_is_sell_found and order_tag == "g1":
          grind_1_sub_grind_count += 1
          grind_1_total_amount += order.safe_filled
          grind_1_total_cost += order.safe_filled * order.safe_price
          grind_1_buy_orders.append(order.id)
          if not grind_1_found:
            grind_1_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_1_found = True
        elif not grind_2_is_sell_found and order_tag == "g2":
          grind_2_sub_grind_count += 1
          grind_2_total_amount += order.safe_filled
          grind_2_total_cost += order.safe_filled * order.safe_price
          grind_2_buy_orders.append(order.id)
          if not grind_2_found:
            grind_2_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_2_found = True
        elif not grind_3_is_sell_found and order_tag == "g3":
          grind_3_sub_grind_count += 1
          grind_3_total_amount += order.safe_filled
          grind_3_total_cost += order.safe_filled * order.safe_price
          grind_3_buy_orders.append(order.id)
          if not grind_3_found:
            grind_3_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_3_found = True
        elif not grind_4_is_sell_found and order_tag == "g4":
          grind_4_sub_grind_count += 1
          grind_4_total_amount += order.safe_filled
          grind_4_total_cost += order.safe_filled * order.safe_price
          grind_4_buy_orders.append(order.id)
          if not grind_4_found:
            grind_4_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_4_found = True
        elif not grind_5_is_sell_found and order_tag == "g5":
          grind_5_sub_grind_count += 1
          grind_5_total_amount += order.safe_filled
          grind_5_total_cost += order.safe_filled * order.safe_price
          grind_5_buy_orders.append(order.id)
          if not grind_5_found:
            grind_5_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            grind_5_found = True
        elif not rebuy_is_sell_found and order_tag not in [
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "dl1",
          "dl2",
          "gd1",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "gm0",
          "gmd0",
        ]:
          rebuy_sub_grind_count += 1
          rebuy_total_amount += order.safe_filled
          rebuy_total_cost += order.safe_filled * order.safe_price
          rebuy_buy_orders.append(order.id)
          if not rebuy_found:
            rebuy_distance_ratio = (exit_rate - order.safe_price) / order.safe_price
            rebuy_found = True
      elif order.ft_order_side == "buy":
        if (
          order is filled_exits[-1]
          and (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake
        ):
          partial_sell = True
          break
        order_tag = ""
        if has_order_tags:
          if order.ft_order_tag is not None:
            sell_order_tag = order.ft_order_tag
            order_mode = sell_order_tag.split(" ", 1)
            if len(order_mode) > 0:
              order_tag = order_mode[0]
        if order_tag == "g1":
          grind_1_is_sell_found = True
        elif order_tag == "g2":
          grind_2_is_sell_found = True
        elif order_tag == "g3":
          grind_3_is_sell_found = True
        elif order_tag == "g4":
          grind_4_is_sell_found = True
        elif order_tag == "g5":
          grind_5_is_sell_found = True
        elif order_tag in ["d", "d1", "dd0", "ddl1", "ddl2", "dd1", "dd2", "dd3", "dd4", "dd5", "dd6"]:
          is_derisk = True
          if order_tag in ["d1"]:
            is_derisk_1 = True
          grind_1_is_sell_found = True
          grind_2_is_sell_found = True
          grind_3_is_sell_found = True
          grind_4_is_sell_found = True
          grind_5_is_sell_found = True
          rebuy_is_sell_found = True
        elif order_tag not in [
          "p",
          "g1",
          "g2",
          "g3",
          "g4",
          "g5",
          "g6",
          "dl1",
          "dl2",
          "gd1",
          "gd2",
          "gd3",
          "gd4",
          "gd5",
          "gd6",
          "gm0",
          "gmd0",
        ]:
          rebuy_is_sell_found = True
        if not is_derisk:
          start_amount = filled_orders[0].safe_filled
          current_amount = 0.0
          for order2 in filled_orders:
            if order2.ft_order_side == "sell":
              current_amount += order2.safe_filled
            elif order2.ft_order_side == "buy":
              current_amount -= order2.safe_filled
            if order2 is order:
              if current_amount < (start_amount * 0.95):
                is_derisk = True
        # found sells for all modes
        if (
          rebuy_is_sell_found
          and grind_1_is_sell_found
          and grind_2_is_sell_found
          and grind_3_is_sell_found
          and grind_4_is_sell_found
          and grind_5_is_sell_found
        ):
          break

    # The trade already de-risked
    if is_derisk:
      return None, "", is_derisk
    if not has_order_tags and len(filled_exits) > 0:
      return None, "", is_derisk

    if rebuy_sub_grind_count > 0:
      rebuy_current_open_rate = rebuy_total_cost / rebuy_total_amount
      rebuy_current_grind_stake = rebuy_total_amount * exit_rate * (1 + trade.fee_close)
      rebuy_current_grind_stake_profit = rebuy_total_cost - rebuy_current_grind_stake
    if grind_1_sub_grind_count > 0:
      grind_1_current_open_rate = grind_1_total_cost / grind_1_total_amount
      grind_1_current_grind_stake = grind_1_total_amount * exit_rate * (1 + trade.fee_close)
      grind_1_current_grind_stake_profit = grind_1_total_cost - grind_1_current_grind_stake
    if grind_2_sub_grind_count > 0:
      grind_2_current_open_rate = grind_2_total_cost / grind_2_total_amount
      grind_2_current_grind_stake = grind_2_total_amount * exit_rate * (1 + trade.fee_close)
      grind_2_current_grind_stake_profit = grind_2_total_cost - grind_2_current_grind_stake
    if grind_3_sub_grind_count > 0:
      grind_3_current_open_rate = grind_3_total_cost / grind_3_total_amount
      grind_3_current_grind_stake = grind_3_total_amount * exit_rate * (1 + trade.fee_close)
      grind_3_current_grind_stake_profit = grind_3_total_cost - grind_3_current_grind_stake
    if grind_4_sub_grind_count > 0:
      grind_4_current_open_rate = grind_4_total_cost / grind_4_total_amount
      grind_4_current_grind_stake = grind_4_total_amount * exit_rate * (1 + trade.fee_close)
      grind_4_current_grind_stake_profit = grind_4_total_cost - grind_4_current_grind_stake
    if grind_5_sub_grind_count > 0:
      grind_5_current_open_rate = grind_5_total_cost / grind_5_total_amount
      grind_5_current_grind_stake = grind_5_total_amount * exit_rate * (1 + trade.fee_close)
      grind_5_current_grind_stake_profit = grind_5_total_cost - grind_5_current_grind_stake

    num_open_grinds = (
      grind_1_sub_grind_count
      + grind_2_sub_grind_count
      + grind_3_sub_grind_count
      + grind_4_sub_grind_count
      + grind_5_sub_grind_count
    )

    fee_open_rate = trade.fee_open if self.custom_fee_open_rate is None else self.custom_fee_open_rate
    fee_close_rate = trade.fee_close if self.custom_fee_close_rate is None else self.custom_fee_close_rate

    # Sell remaining if partial fill on exit
    if partial_sell:
      order = filled_exits[-1]
      sell_amount = order.safe_remaining * exit_rate / trade.leverage
      if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
        sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        self.dp.send_msg(
          f"Exit (remaining) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {order.safe_remaining} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "p"
        if has_order_tags:
          if order.ft_order_tag is not None:
            order_tag = order.ft_order_tag
        return -ft_sell_amount, order_tag, is_derisk

    is_short_grind_buy = self.short_grind_buy(last_candle, previous_candle, slice_profit)

    # Rebuy
    if (not partial_sell) and (not rebuy_is_sell_found) and (rebuy_sub_grind_count < max_rebuy_sub_grinds):
      if (
        (0 <= rebuy_sub_grind_count < max_rebuy_sub_grinds)
        and (slice_profit_entry < regular_mode_rebuy_sub_thresholds[rebuy_sub_grind_count])
        and (
          (-rebuy_distance_ratio if (rebuy_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_rebuy_sub_thresholds[rebuy_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=12) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.06))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (last_candle["close"] < (last_candle["close_min_12"] * 1.06))
          and (last_candle["close"] < (last_candle["close_min_24"] * 1.08))
          and (last_candle["close"] < (last_candle["close_min_48"] * 1.10))
          and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.12))
          and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.14))
          and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.16))
          and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.18))
          and (last_candle["btc_pct_close_min_72_5m"] > -0.03)
          and (last_candle["btc_pct_close_min_24_5m"] > -0.03)
        )
        and (
          is_short_grind_buy
          or (
            (last_candle["RSI_3"] < 70.0)
            and (last_candle["RSI_3_15m"] < 70.0)
            and (last_candle["RSI_3_1h"] < 70.0)
            and (last_candle["RSI_3_4h"] < 70.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["zlma_50_dec_1h"] == True)
            and (last_candle["zlma_50_dec_4h"] == True)
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_rebuy_stakes[rebuy_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount > max_stake:
          buy_amount = max_stake
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        self.dp.send_msg(
          f"Rebuy (r) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"Rebuy (r) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        order_tag = "r"
        return buy_amount, order_tag, is_derisk

    # Gringing g1
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_1_sub_grind_count < max_grind_1_sub_grinds):
      if (
        (
          (-grind_1_distance_ratio if (grind_1_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_1_sub_thresholds[grind_1_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
              # and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.24))
              # and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.30))
            )
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 84.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 80.0)
                and (last_candle["RSI_3_4h"] < 80.0)
                and (last_candle["RSI_14"] > 64.0)
                # and (last_candle["zlma_50_dec_1h"] == True)
                # and (last_candle["zlma_50_dec_4h"] == True)
                and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
              )
              or (
                (last_candle["RSI_14"] > 64.0)
                and (previous_candle["RSI_3"] < 90.0)
                and (last_candle["RSI_3_15m"] < 90.0)
                and (last_candle["RSI_3_1h"] < 90.0)
                and (last_candle["RSI_3_4h"] < 90.0)
                and (last_candle["close"] > (last_candle["SMA_16"] * 1.014))
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            # and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_1_stakes[grind_1_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_1_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
          grind_profit_stake = grind_1_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g1"
        return buy_amount, order_tag, is_derisk

    if (
      self.is_futures_mode
      and has_order_tags
      and (not partial_sell)
      and slice_profit > (0.65 / trade.leverage)
      and (grind_1_sub_grind_count < max_grind_1_sub_grinds)
    ):
      buy_amount = (
        slice_amount
        * regular_mode_grind_1_stakes[grind_1_sub_grind_count]
        / (trade.leverage if self.is_futures_mode else 1.0)
      )
      if buy_amount < (min_stake * 1.5):
        buy_amount = min_stake * 1.5
      if buy_amount > max_stake:
        return None, "", is_derisk
      grind_profit = 0.0
      grind_profit_stake = 0.0
      if grind_1_sub_grind_count > 0:
        grind_profit = -(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
        grind_profit_stake = grind_1_current_grind_stake_profit
      self.dp.send_msg(
        f"Grinding entry (g1) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      log.info(
        f"Grinding entry (g1) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_1_current_grind_stake_profit} {self.config['stake_currency']})"
      )
      order_tag = "g1"
      return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_1_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_1_current_open_rate) / grind_1_current_open_rate
      if grind_profit > (regular_mode_grind_1_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_1_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_1_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g1"
          for grind_entry_id in grind_1_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Gringing g2
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_2_sub_grind_count < max_grind_2_sub_grinds):
      if (
        (
          (-grind_2_distance_ratio if (grind_2_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_2_sub_thresholds[grind_2_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
              # and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.24))
              # and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.30))
            )
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 84.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 80.0)
                and (last_candle["RSI_3_4h"] < 80.0)
                and (last_candle["RSI_14"] > 64.0)
                # and (last_candle["zlma_50_dec_1h"] == True)
                # and (last_candle["zlma_50_dec_4h"] == True)
                and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
              )
              or (
                (last_candle["RSI_14"] > 64.0)
                and (previous_candle["RSI_3"] < 90.0)
                and (last_candle["RSI_3_15m"] < 90.0)
                and (last_candle["RSI_3_1h"] < 90.0)
                and (last_candle["RSI_3_4h"] < 90.0)
                and (last_candle["close"] > (last_candle["SMA_16"] * 1.014))
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            # and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_2_stakes[grind_2_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_2_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
          grind_profit_stake = grind_2_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g2) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g2) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_2_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g2"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_2_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_2_current_open_rate) / grind_2_current_open_rate
      if grind_profit > (regular_mode_grind_2_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_2_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g2) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g2) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_2_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g2"
          for grind_entry_id in grind_2_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Gringing g3
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_3_sub_grind_count < max_grind_3_sub_grinds):
      if (
        (
          (-grind_3_distance_ratio if (grind_3_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_3_sub_thresholds[grind_3_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
              # and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.24))
              # and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.30))
            )
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 88.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 84.0)
                and (last_candle["RSI_3_4h"] < 84.0)
                and (last_candle["RSI_14"] > 64.0)
                # and (last_candle["zlma_50_dec_1h"] == True)
                # and (last_candle["zlma_50_dec_4h"] == True)
                and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
              )
              or (
                (last_candle["RSI_14"] > 64.0)
                and (previous_candle["RSI_3"] < 90.0)
                and (last_candle["RSI_3_15m"] < 90.0)
                and (last_candle["RSI_3_1h"] < 90.0)
                and (last_candle["RSI_3_4h"] < 90.0)
                and (last_candle["close"] > (last_candle["SMA_16"] * 1.014))
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            # and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_3_stakes[grind_3_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_3_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
          grind_profit_stake = grind_3_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g3) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g3) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_3_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g3"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_3_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_3_current_open_rate) / grind_3_current_open_rate
      if grind_profit > (regular_mode_grind_3_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_3_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g3) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g3) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_3_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g3"
          for grind_entry_id in grind_3_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Gringing g4
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_4_sub_grind_count < max_grind_4_sub_grinds):
      if (
        (
          (-grind_4_distance_ratio if (grind_4_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_4_sub_thresholds[grind_4_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
              # and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.24))
              # and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.30))
            )
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 88.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 84.0)
                and (last_candle["RSI_3_4h"] < 84.0)
                and (last_candle["RSI_14"] > 64.0)
                # and (last_candle["zlma_50_dec_1h"] == True)
                # and (last_candle["zlma_50_dec_4h"] == True)
                and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
              )
              or (
                (last_candle["RSI_14"] > 64.0)
                and (previous_candle["RSI_3"] < 90.0)
                and (last_candle["RSI_3_15m"] < 90.0)
                and (last_candle["RSI_3_1h"] < 90.0)
                and (last_candle["RSI_3_4h"] < 90.0)
                and (last_candle["close"] > (last_candle["SMA_16"] * 1.014))
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            # and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_4_stakes[grind_4_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_4_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
          grind_profit_stake = grind_4_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g4) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g4) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_4_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g4"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_4_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_4_current_open_rate) / grind_4_current_open_rate
      if grind_profit > (regular_mode_grind_4_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_4_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g4) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g4) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_4_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g4"
          for grind_entry_id in grind_4_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # Gringing g5
    # Grinding entry
    if has_order_tags and (not partial_sell) and (grind_5_sub_grind_count < max_grind_5_sub_grinds):
      if (
        (
          (-grind_5_distance_ratio if (grind_5_sub_grind_count > 0) else profit_init_ratio)
          < (regular_mode_grind_5_sub_thresholds[grind_5_sub_grind_count])
        )
        and (current_time - timedelta(minutes=10) > filled_entries[-1].order_filled_utc)
        and ((current_time - timedelta(hours=2) > filled_orders[-1].order_filled_utc) or (slice_profit > 0.02))
        and (
          (num_open_grinds == 0)
          or (current_time - timedelta(hours=6) > filled_orders[-1].order_filled_utc)
          or (slice_profit > 0.06)
        )
        and ((num_open_grinds == 0) or (slice_profit > 0.03))
        and (
          (last_candle["protections_short_rebuy"] == True)
          and (last_candle["protections_short_global"] == True)
          and (last_candle["global_protections_short_pump"] == True)
          and (last_candle["global_protections_short_dump"] == True)
        )
        and (
          (
            (
              (last_candle["close"] < (last_candle["close_min_12"] * 1.16))
              and (last_candle["close"] < (last_candle["close_min_24"] * 1.20))
              and (last_candle["close"] < (last_candle["close_min_48"] * 1.24))
              and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.26))
              and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.30))
              # and (last_candle["close"] < (last_candle["low_min_6_1d"] * 1.24))
              # and (last_candle["close"] < (last_candle["low_min_12_1d"] * 1.30))
            )
            and (
              is_short_grind_buy
              or (
                (last_candle["RSI_3"] < 88.0)
                and (last_candle["RSI_3_15m"] < 84.0)
                and (last_candle["RSI_3_1h"] < 84.0)
                and (last_candle["RSI_3_4h"] < 84.0)
                and (last_candle["RSI_14"] > 64.0)
                # and (last_candle["zlma_50_dec_1h"] == True)
                # and (last_candle["zlma_50_dec_4h"] == True)
                and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
              )
              or (
                (last_candle["RSI_14"] > 64.0)
                and (previous_candle["RSI_3"] < 90.0)
                and (last_candle["RSI_3_15m"] < 90.0)
                and (last_candle["RSI_3_1h"] < 90.0)
                and (last_candle["RSI_3_4h"] < 90.0)
                and (last_candle["close"] > (last_candle["SMA_16"] * 1.014))
              )
            )
          )
          or (
            (slice_profit > 0.06)
            and (last_candle["RSI_3"] < 90.0)
            and (last_candle["RSI_3_15m"] < 90.0)
            # and (last_candle["RSI_14"] < 72.0)
            and (last_candle["RSI_14"] > 64.0)
            and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
          )
        )
      ):
        buy_amount = (
          slice_amount
          * regular_mode_grind_5_stakes[grind_5_sub_grind_count]
          / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        if buy_amount > max_stake:
          return None, "", is_derisk
        grind_profit = 0.0
        grind_profit_stake = 0.0
        if grind_5_sub_grind_count > 0:
          grind_profit = -(exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
          grind_profit_stake = grind_5_current_grind_stake_profit
        self.dp.send_msg(
          f"Grinding entry (g5) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        log.info(
          f"Grinding entry (g5) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_5_current_grind_stake_profit} {self.config['stake_currency']})"
        )
        order_tag = "g5"
        return buy_amount, order_tag, is_derisk

    # Grinding Exit
    if has_order_tags and grind_5_sub_grind_count > 0:
      grind_profit = -(exit_rate - grind_5_current_open_rate) / grind_5_current_open_rate
      if grind_profit > (regular_mode_grind_5_profit_threshold + fee_open_rate + fee_close_rate):
        sell_amount = grind_5_total_amount * exit_rate / trade.leverage
        if ((current_stake_amount / trade.leverage) - sell_amount) < (min_stake * 1.55):
          sell_amount = (trade.amount * exit_rate / trade.leverage) - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Grinding exit (g5) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          log.info(
            f"Grinding exit (g5) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Coin amount: {grind_5_total_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}% | Grind profit: {(grind_profit * 100.0):.2f}% ({grind_profit * sell_amount * trade.leverage} {self.config['stake_currency']})"
          )
          order_tag = "g5"
          for grind_entry_id in grind_5_buy_orders:
            order_tag += " " + str(grind_entry_id)
          return -ft_sell_amount, order_tag, is_derisk

    # De-risk
    if profit_stake < (
      slice_amount
      * (
        (self.regular_mode_derisk_futures if self.is_futures_mode else self.regular_mode_derisk_spot)
        if (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 3, 19) or is_backtest)
        else (self.regular_mode_derisk_futures_old if self.is_futures_mode else self.regular_mode_derisk_spot_old)
      )
      # / (trade.leverage if self.is_futures_mode else 1.0)
    ):
      sell_amount = trade.amount * exit_rate / trade.leverage - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d", is_derisk

    # De-risk level 1
    if (
      has_order_tags
      and not is_derisk_1
      and (trade.open_date_utc.replace(tzinfo=None) >= datetime(2024, 4, 5) or is_backtest)
      and profit_stake
      < (
        slice_amount
        * (self.regular_mode_derisk_1_futures if self.is_futures_mode else self.regular_mode_derisk_1_spot)
        # / (trade.leverage if self.is_futures_mode else 1.0)
      )
    ):
      sell_amount = trade.amount * exit_rate / trade.leverage - (min_stake * 1.55)
      ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
      if sell_amount > min_stake and ft_sell_amount > min_stake:
        grind_profit = 0.0
        self.dp.send_msg(
          f"De-risk (d1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"De-risk (d1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        return -ft_sell_amount, "d1", is_derisk

    return None, "", is_derisk

  # Short Rebuy Adjust Trade Position
  # ---------------------------------------------------------------------------------------------
  def short_rebuy_adjust_trade_position(
    self,
    trade: Trade,
    enter_tags,
    current_time: datetime,
    current_rate: float,
    current_profit: float,
    min_stake: Optional[float],
    max_stake: float,
    current_entry_rate: float,
    current_exit_rate: float,
    current_entry_profit: float,
    current_exit_profit: float,
    **kwargs,
  ) -> Optional[float]:
    # min/max stakes include leverage. The return amounts is before leverage.
    min_stake /= trade.leverage
    max_stake /= trade.leverage
    df, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
    if len(df) < 2:
      return None
    last_candle = df.iloc[-1].squeeze()
    previous_candle = df.iloc[-2].squeeze()

    filled_orders = trade.select_filled_orders()
    filled_entries = trade.select_filled_orders(trade.entry_side)
    filled_exits = trade.select_filled_orders(trade.exit_side)
    count_of_entries = trade.nr_of_successful_entries
    count_of_exits = trade.nr_of_successful_exits

    if count_of_entries == 0:
      return None

    has_order_tags = False
    if hasattr(filled_orders[0], "ft_order_tag"):
      has_order_tags = True

    # The first exit is de-risk (providing the trade is still open)
    if count_of_exits > 0:
      return self.short_grind_adjust_trade_position(
        trade,
        enter_tags,
        current_time,
        current_rate,
        current_profit,
        min_stake,
        max_stake,
        current_entry_rate,
        current_exit_rate,
        current_entry_profit,
        current_exit_profit,
      )

    exit_rate = current_rate
    if self.dp.runmode.value in ("live", "dry_run"):
      ticker = self.dp.ticker(trade.pair)
      if ("bid" in ticker) and ("ask" in ticker):
        if trade.is_short:
          if self.config["exit_pricing"]["price_side"] in ["ask", "other"]:
            if ticker["ask"] is not None:
              exit_rate = ticker["ask"]
        else:
          if self.config["exit_pricing"]["price_side"] in ["bid", "other"]:
            if ticker["bid"] is not None:
              exit_rate = ticker["bid"]

    profit_stake, profit_ratio, profit_current_stake_ratio, profit_init_ratio = self.calc_total_profit(
      trade, filled_entries, filled_exits, exit_rate
    )

    slice_amount = filled_entries[0].cost
    slice_profit = (exit_rate - filled_orders[-1].safe_price) / filled_orders[-1].safe_price
    slice_profit_entry = (exit_rate - filled_entries[-1].safe_price) / filled_entries[-1].safe_price
    slice_profit_exit = (
      ((exit_rate - filled_exits[-1].safe_price) / filled_exits[-1].safe_price) if count_of_exits > 0 else 0.0
    )

    current_stake_amount = trade.amount * current_rate

    is_rebuy = False

    rebuy_mode_stakes = self.rebuy_mode_stakes_futures if self.is_futures_mode else self.rebuy_mode_stakes_spot
    max_sub_grinds = len(rebuy_mode_stakes)
    rebuy_mode_sub_thresholds = (
      self.rebuy_mode_thresholds_futures if self.is_futures_mode else self.rebuy_mode_thresholds_spot
    )
    partial_sell = False
    sub_grind_count = 0
    total_amount = 0.0
    total_cost = 0.0
    current_open_rate = 0.0
    current_grind_stake = 0.0
    current_grind_stake_profit = 0.0
    for order in reversed(filled_orders):
      if (order.ft_order_side == "buy") and (order is not filled_orders[0]):
        sub_grind_count += 1
        total_amount += order.safe_filled
        total_cost += order.safe_filled * order.safe_price
      elif order.ft_order_side == "sell":
        if (order.safe_remaining * exit_rate / (trade.leverage if self.is_futures_mode else 1.0)) > min_stake:
          partial_sell = True
        break
    if sub_grind_count > 0:
      current_open_rate = total_cost / total_amount
      current_grind_stake = total_amount * exit_rate * (1 - trade.fee_close)
      current_grind_stake_profit = current_grind_stake - total_cost

    if (not partial_sell) and (sub_grind_count < max_sub_grinds):
      if (
        ((0 <= sub_grind_count < max_sub_grinds) and (slice_profit_entry < rebuy_mode_sub_thresholds[sub_grind_count]))
        and (last_candle["protections_short_global"] == True)
        and (last_candle["protections_short_rebuy"] == True)
        and (last_candle["global_protections_short_pump"] == True)
        and (last_candle["global_protections_short_dump"] == True)
        and (
          (last_candle["close"] < (last_candle["close_min_12"] * 1.06))
          and (last_candle["close"] < (last_candle["close_min_24"] * 1.08))
          and (last_candle["close"] < (last_candle["close_min_48"] * 1.10))
          and (last_candle["close"] < (last_candle["low_min_24_1h"] * 1.12))
          and (last_candle["close"] < (last_candle["low_min_48_1h"] * 1.14))
          and (last_candle["btc_pct_close_min_72_5m"] > 0.03)
          and (last_candle["btc_pct_close_min_24_5m"] > 0.03)
        )
        and (
          (last_candle["RSI_3"] < 90.0)
          and (last_candle["RSI_3_15m"] < 90.0)
          and (last_candle["RSI_3_1h"] < 90.0)
          and (last_candle["RSI_3_4h"] < 90.0)
          and (last_candle["RSI_14"] > 64.0)
          and (last_candle["close"] > (last_candle["EMA_26"] * 1.012))
        )
      ):
        buy_amount = (
          slice_amount * rebuy_mode_stakes[sub_grind_count] / (trade.leverage if self.is_futures_mode else 1.0)
        )
        if buy_amount > max_stake:
          buy_amount = max_stake
        if buy_amount < (min_stake * 1.5):
          buy_amount = min_stake * 1.5
        self.dp.send_msg(
          f"Rebuy (r) [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        log.info(
          f"Rebuy (r) [{current_time}] [{trade.pair}] | Rate: {current_rate} | Stake amount: {buy_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
        )
        if has_order_tags:
          return buy_amount, "r"
        else:
          return buy_amount

      if profit_stake < (
        slice_amount
        * (self.rebuy_mode_derisk_futures if self.is_futures_mode else self.rebuy_mode_derisk_spot)
        / (trade.leverage if self.is_futures_mode else 1.0)
      ):
        sell_amount = trade.amount * exit_rate / trade.leverage - (min_stake * 1.55)
        ft_sell_amount = sell_amount * trade.leverage * (trade.stake_amount / trade.amount) / exit_rate
        if sell_amount > min_stake and ft_sell_amount > min_stake:
          self.dp.send_msg(
            f"Rebuy de-risk (d1) [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
          )
          log.info(
            f"Rebuy de-risk (d1) [{current_time}] [{trade.pair}] | Rate: {exit_rate} | Stake amount: {sell_amount} | Profit (stake): {profit_stake} | Profit: {(profit_ratio * 100.0):.2f}%"
          )
          if has_order_tags:
            return -ft_sell_amount, "d1"
          else:
            return -ft_sell_amount

    return None

  ###############################################################################################
  # SHORT GRIND FUNCTIONS ENDS HERE
  ###############################################################################################


# +---------------------------------------------------------------------------+
# |                              Custom Indicators                            |
# +---------------------------------------------------------------------------+


# Range midpoint acts as Support
# ---------------------------------------------------------------------------------------------
def is_support(row_data) -> bool:
  conditions = []
  for row in range(len(row_data) - 1):
    if row < len(row_data) // 2:
      conditions.append(row_data[row] > row_data[row + 1])
    else:
      conditions.append(row_data[row] < row_data[row + 1])
  result = reduce(lambda x, y: x & y, conditions)
  return result


# Range midpoint acts as Resistance
# ---------------------------------------------------------------------------------------------
def is_resistance(row_data) -> bool:
  conditions = []
  for row in range(len(row_data) - 1):
    if row < len(row_data) // 2:
      conditions.append(row_data[row] < row_data[row + 1])
    else:
      conditions.append(row_data[row] > row_data[row + 1])
  result = reduce(lambda x, y: x & y, conditions)
  return result


# Elliot Wave Oscillator
# ---------------------------------------------------------------------------------------------
def ewo(df, ema1_length=5, ema2_length=35):
  ema1 = ta.EMA(df, timeperiod=ema1_length)
  ema2 = ta.EMA(df, timeperiod=ema2_length)
  emadiff = (ema1 - ema2) / df["close"] * 100.0
  return emadiff


# Pivot Points - 3 variants - daily recommended
# ---------------------------------------------------------------------------------------------
def pivot_points(df: DataFrame, mode="fibonacci") -> Series:
  if mode == "simple":
    hlc3_pivot = (df["high"] + df["low"] + df["close"]).shift(1) / 3
    res1 = hlc3_pivot * 2 - df["low"].shift(1)
    sup1 = hlc3_pivot * 2 - df["high"].shift(1)
    res2 = hlc3_pivot + (df["high"] - df["low"]).shift()
    sup2 = hlc3_pivot - (df["high"] - df["low"]).shift()
    res3 = hlc3_pivot * 2 + (df["high"] - 2 * df["low"]).shift()
    sup3 = hlc3_pivot * 2 - (2 * df["high"] - df["low"]).shift()
    return hlc3_pivot, res1, res2, res3, sup1, sup2, sup3
  elif mode == "fibonacci":
    hlc3_pivot = (df["high"] + df["low"] + df["close"]).shift(1) / 3
    hl_range = (df["high"] - df["low"]).shift(1)
    res1 = hlc3_pivot + 0.382 * hl_range
    sup1 = hlc3_pivot - 0.382 * hl_range
    res2 = hlc3_pivot + 0.618 * hl_range
    sup2 = hlc3_pivot - 0.618 * hl_range
    res3 = hlc3_pivot + 1 * hl_range
    sup3 = hlc3_pivot - 1 * hl_range
    return hlc3_pivot, res1, res2, res3, sup1, sup2, sup3
  elif mode == "DeMark":
    demark_pivot_lt = df["low"] * 2 + df["high"] + df["close"]
    demark_pivot_eq = df["close"] * 2 + df["low"] + df["high"]
    demark_pivot_gt = df["high"] * 2 + df["low"] + df["close"]
    demark_pivot = np.where(
      (df["close"] < df["open"]),
      demark_pivot_lt,
      np.where((df["close"] > df["open"]), demark_pivot_gt, demark_pivot_eq),
    )
    dm_pivot = demark_pivot / 4
    dm_res = demark_pivot / 2 - df["low"]
    dm_sup = demark_pivot / 2 - df["high"]
    return dm_pivot, dm_res, dm_sup


# Heikin Ashi candles
# ---------------------------------------------------------------------------------------------
def heikin_ashi(df, smooth_inputs=False, smooth_outputs=False, length=10):
  df = df[["open", "close", "high", "low"]].copy().fillna(0)
  if smooth_inputs:
    df["open_s"] = ta.EMA(df["open"], timeframe=length)
    df["high_s"] = ta.EMA(df["high"], timeframe=length)
    df["low_s"] = ta.EMA(df["low"], timeframe=length)
    df["close_s"] = ta.EMA(df["close"], timeframe=length)

    open_ha = (df["open_s"].shift(1) + df["close_s"].shift(1)) / 2
    high_ha = df.loc[:, ["high_s", "open_s", "close_s"]].max(axis=1)
    low_ha = df.loc[:, ["low_s", "open_s", "close_s"]].min(axis=1)
    close_ha = (df["open_s"] + df["high_s"] + df["low_s"] + df["close_s"]) / 4
  else:
    open_ha = (df["open"].shift(1) + df["close"].shift(1)) / 2
    high_ha = df.loc[:, ["high", "open", "close"]].max(axis=1)
    low_ha = df.loc[:, ["low", "open", "close"]].min(axis=1)
    close_ha = (df["open"] + df["high"] + df["low"] + df["close"]) / 4

  open_ha = open_ha.fillna(0)
  high_ha = high_ha.fillna(0)
  low_ha = low_ha.fillna(0)
  close_ha = close_ha.fillna(0)

  if smooth_outputs:
    open_sha = ta.EMA(open_ha, timeframe=length)
    high_sha = ta.EMA(high_ha, timeframe=length)
    low_sha = ta.EMA(low_ha, timeframe=length)
    close_sha = ta.EMA(close_ha, timeframe=length)

    return open_sha, close_sha, low_sha
  else:
    return open_ha, close_ha, low_ha


# Peak Percentage Change
# ---------------------------------------------------------------------------------------------
def range_percent_change(self, df: DataFrame, method, length: int) -> float:
  """
  Rolling Percentage Change Maximum across interval.

  :param df: DataFrame The original OHLC df
  :param method: High to Low / Open to Close
  :param length: int The length to look back
  """
  if method == "HL":
    return (df["high"].rolling(length).max() - df["low"].rolling(length).min()) / df["low"].rolling(length).min()
  elif method == "OC":
    return (df["open"].rolling(length).max() - df["close"].rolling(length).min()) / df["close"].rolling(length).min()
  else:
    raise ValueError(f"Method {method} not defined!")


# Percentage distance to top peak
# ---------------------------------------------------------------------------------------------
def top_percent_change(self, df: DataFrame, length: int) -> float:
  """
  Percentage change of the current close from the range maximum Open price

  :param df: DataFrame The original OHLC df
  :param length: int The length to look back
  """
  if length == 0:
    return (df["open"] - df["close"]) / df["close"]
  else:
    return (df["open"].rolling(length).max() - df["close"]) / df["close"]


# +---------------------------------------------------------------------------+
# |                              Classes                                      |
# +---------------------------------------------------------------------------+


# Cache Class
# ---------------------------------------------------------------------------------------------
class Cache:
  def __init__(self, path):
    self.path = path
    self.data = {}
    self._mtime = None
    self._previous_data = {}
    try:
      self.load()
    except FileNotFoundError:
      pass

  @staticmethod
  def rapidjson_load_kwargs():
    return {"number_mode": rapidjson.NM_NATIVE, "parse_mode": rapidjson.PM_COMMENTS | rapidjson.PM_TRAILING_COMMAS}

  @staticmethod
  def rapidjson_dump_kwargs():
    return {"number_mode": rapidjson.NM_NATIVE}

  def load(self):
    if not self._mtime or self.path.stat().st_mtime_ns != self._mtime:
      self._load()

  def save(self):
    if self.data != self._previous_data:
      self._save()

  def process_loaded_data(self, data):
    return data

  def _load(self):
    # This method only exists to simplify unit testing
    with self.path.open("r") as rfh:
      try:
        data = rapidjson.load(rfh, **self.rapidjson_load_kwargs())
      except rapidjson.JSONDecodeError as exc:
        log.error("Failed to load JSON from %s: %s", self.path, exc)
      else:
        self.data = self.process_loaded_data(data)
        self._previous_data = copy.deepcopy(self.data)
        self._mtime = self.path.stat().st_mtime_ns

  def _save(self):
    # This method only exists to simplify unit testing
    rapidjson.dump(self.data, self.path.open("w"), **self.rapidjson_dump_kwargs())
    self._mtime = self.path.stat().st_mtime
    self._previous_data = copy.deepcopy(self.data)


class HoldsCache(Cache):
  @staticmethod
  def rapidjson_load_kwargs():
    return {
      "number_mode": rapidjson.NM_NATIVE,
      "parse_mode": rapidjson.PM_COMMENTS | rapidjson.PM_TRAILING_COMMAS,
      "object_hook": HoldsCache._object_hook,
    }

  @staticmethod
  def rapidjson_dump_kwargs():
    return {
      "number_mode": rapidjson.NM_NATIVE,
      "mapping_mode": rapidjson.MM_COERCE_KEYS_TO_STRINGS,
    }

  def save(self):
    raise RuntimeError("The holds cache does not allow programatical save")

  def process_loaded_data(self, data):
    trade_ids = data.get("trade_ids")
    trade_pairs = data.get("trade_pairs")

    if not trade_ids and not trade_pairs:
      return data

    open_trades = {}
    for trade in Trade.get_trades_proxy(is_open=True):
      open_trades[trade.id] = open_trades[trade.pair] = trade

    r_trade_ids = {}
    if trade_ids:
      if isinstance(trade_ids, dict):
        # New syntax
        for trade_id, profit_ratio in trade_ids.items():
          if not isinstance(trade_id, int):
            log.error("The trade_id(%s) defined under 'trade_ids' in %s is not an integer", trade_id, self.path)
            continue
          if not isinstance(profit_ratio, float):
            log.error(
              "The 'profit_ratio' config value(%s) for trade_id %s in %s is not a float",
              profit_ratio,
              trade_id,
              self.path,
            )
          if trade_id in open_trades:
            formatted_profit_ratio = f"{profit_ratio * 100}%"
            log.warning(
              "The trade %s is configured to HOLD until the profit ratio of %s is met",
              open_trades[trade_id],
              formatted_profit_ratio,
            )
            r_trade_ids[trade_id] = profit_ratio
          else:
            log.warning(
              "The trade_id(%s) is no longer open. Please remove it from 'trade_ids' in %s",
              trade_id,
              self.path,
            )
      else:
        # Initial Syntax
        profit_ratio = data.get("profit_ratio")
        if profit_ratio:
          if not isinstance(profit_ratio, float):
            log.error("The 'profit_ratio' config value(%s) in %s is not a float", profit_ratio, self.path)
        else:
          profit_ratio = 0.005
        formatted_profit_ratio = f"{profit_ratio * 100}%"
        for trade_id in trade_ids:
          if not isinstance(trade_id, int):
            log.error("The trade_id(%s) defined under 'trade_ids' in %s is not an integer", trade_id, self.path)
            continue
          if trade_id in open_trades:
            log.warning(
              "The trade %s is configured to HOLD until the profit ratio of %s is met",
              open_trades[trade_id],
              formatted_profit_ratio,
            )
            r_trade_ids[trade_id] = profit_ratio
          else:
            log.warning(
              "The trade_id(%s) is no longer open. Please remove it from 'trade_ids' in %s",
              trade_id,
              self.path,
            )

    r_trade_pairs = {}
    if trade_pairs:
      for trade_pair, profit_ratio in trade_pairs.items():
        if not isinstance(trade_pair, str):
          log.error("The trade_pair(%s) defined under 'trade_pairs' in %s is not a string", trade_pair, self.path)
          continue
        if "/" not in trade_pair:
          log.error(
            "The trade_pair(%s) defined under 'trade_pairs' in %s does not look like "
            "a valid '<TOKEN_NAME>/<STAKE_CURRENCY>' formatted pair.",
            trade_pair,
            self.path,
          )
          continue
        if not isinstance(profit_ratio, float):
          log.error(
            "The 'profit_ratio' config value(%s) for trade_pair %s in %s is not a float",
            profit_ratio,
            trade_pair,
            self.path,
          )
        formatted_profit_ratio = f"{profit_ratio * 100}%"
        if trade_pair in open_trades:
          log.warning(
            "The trade %s is configured to HOLD until the profit ratio of %s is met",
            open_trades[trade_pair],
            formatted_profit_ratio,
          )
        else:
          log.warning(
            "The trade pair %s is configured to HOLD until the profit ratio of %s is met",
            trade_pair,
            formatted_profit_ratio,
          )
        r_trade_pairs[trade_pair] = profit_ratio

    r_data = {}
    if r_trade_ids:
      r_data["trade_ids"] = r_trade_ids
    if r_trade_pairs:
      r_data["trade_pairs"] = r_trade_pairs
    return r_data

  @staticmethod
  def _object_hook(data):
    _data = {}
    for key, value in data.items():
      try:
        key = int(key)
      except ValueError:
        pass
      _data[key] = value
    return _data
