//+------------------------------------------------------------------+
//|                                    ScalpMicro_10USD.mq5          |
//|  $10 Micro Scalper for MT5 - Quick Scalp with Strict Risk Mgmt  |
//|  Strategy: EMA 9/21 Crossover + RSI(14) + ATR(14) + Spread Filter|
//|  Designed for: EURUSD, GBPUSD, XAUUSD (Gold), Volatility Indices |
//|  Timeframe: M1 / M5 (default M5)                                  |
//|  Author: Arena Workflow - 2026-08-11                              |
//+------------------------------------------------------------------+
#property copyright "Arena Workflow - Micro Scalper $10"
#property link      "https://github.com/dithinmandanna10-hue/workflow"
#property version   "1.30"
#property strict
#property description "Micro scalper optimized for $10 accounts."
#property description "Risk 1-2% per trade, ATR SL/TP, daily loss limit,"
#property description "spread filter, trailing + breakeven."

#include <Trade/Trade.mqh>
CTrade trade;

//--- INPUTS
input group "=== RISK & MONEY MANAGEMENT ( $10 SAFE ) ==="
input double   InpRiskPercent       = 1.5;      // Risk per trade % of balance (1.0-2.0 recommended for $10)
input double   InpFixedLot          = 0.01;     // Fixed lot if auto calc < 0.01 (min lot)
input double   InpMaxLot            = 0.05;     // Max lot cap - PROTECT $10 ACCOUNT (0.05 max)
input double   InpMaxDailyLossPct   = 5.0;      // Max daily loss % -> bot stops for day
input double   InpDailyTargetPct    = 4.0;      // Daily profit target % -> bot stops and locks profit
input int      InpMaxTradesPerDay   = 12;       // Max trades per day
input int      InpMaxConsecutiveLoss= 3;        // Pause after N consecutive losses
input int      InpCoolDownMinutes   = 45;       // Cooldown minutes after loss streak

input group "=== STRATEGY ==="
input ENUM_TIMEFRAMES InpTimeframe  = PERIOD_M5;// Trading timeframe
input int      InpEMAFast           = 9;        // EMA Fast
input int      InpEMASlow           = 21;       // EMA Slow
input int      InpRSIPeriod         = 14;       // RSI Period
input double   InpRSI_BuyMin        = 50.0;     // RSI min for BUY (avoid overbought)
input double   InpRSI_BuyMax        = 68.0;     // RSI max for BUY
input double   InpRSI_SellMin       = 32.0;     // RSI min for SELL
input double   InpRSI_SellMax       = 50.0;     // RSI max for SELL
input int      InpATRPeriod         = 14;       // ATR Period
input double   InpATR_SL_Mult       = 1.8;      // SL = ATR * mult (1.5-2.0)
input double   InpATR_TP_Mult       = 1.2;      // TP = ATR * mult (1.0-1.5 for scalp)
input double   InpMinATRPoints      = 50;       // Min ATR in points (filter flat market)
input double   InpMaxATRPoints      = 800;      // Max ATR in points (filter wild news)

input group "=== EXECUTION & FILTERS ==="
input int      InpMaxSpreadPoints   = 250;      // Max spread in points (e.g., 25 pips for gold = 250 points on 2-digit gold)
input bool     InpUseSpreadFilter   = true;     // Enable spread filter
input bool     InpTradeMonday       = true;
input bool     InpTradeFriday       = true;
input int      InpStartHour         = 0;        // Start hour (broker time) 0-23
input int      InpEndHour           = 23;       // End hour
input bool     InpNoTradeHighImpactNews = false;// Placeholder (manual)
input int      InpMinBarsBetweenTrades = 3;     // Min bars between trades (avoid overtrading)

input group "=== EXIT MANAGEMENT ==="
input bool     InpUseBreakeven      = true;     // Move SL to breakeven
input double   InpBreakevenPlusPoints= 50;      // Breakeven + points (lock small profit)
input double   InpBreakevenTriggerPoints= 100;  // Profit to trigger breakeven (points)
input bool     InpUseTrailing       = true;     // Use trailing stop
input double   InpTrailingStartPoints= 120;     // Trailing start (points)
input double   InpTrailingStepPoints = 60;      // Trailing step (points)
input int      InpMaxHoldMinutes    = 90;       // Max hold time for scalp (close if stuck)

input group "=== SYSTEM ==="
input long     InpMagic             = 101010;   // Magic number
input string   InpComment           = "Micro10$"; // Trade comment

//--- GLOBALS
int handleEMA_Fast, handleEMA_Slow, handleRSI, handleATR;
double dailyStartBalance = 0;
datetime dailyStartDay = 0;
int tradesToday = 0;
int consecutiveLosses = 0;
datetime coolDownUntil = 0;
datetime lastTradeTime = 0;
int lastBars = 0;

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   handleEMA_Fast = iMA(_Symbol, InpTimeframe, InpEMAFast, 0, MODE_EMA, PRICE_CLOSE);
   handleEMA_Slow = iMA(_Symbol, InpTimeframe, InpEMASlow, 0, MODE_EMA, PRICE_CLOSE);
   handleRSI      = iRSI(_Symbol, InpTimeframe, InpRSIPeriod, PRICE_CLOSE);
   handleATR      = iATR(_Symbol, InpTimeframe, InpATRPeriod);

   if(handleEMA_Fast==INVALID_HANDLE || handleEMA_Slow==INVALID_HANDLE || handleRSI==INVALID_HANDLE || handleATR==INVALID_HANDLE)
     {
      Print("Failed to create indicators");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   trade.SetTypeFilling(ORDER_FILLING_IOC);

   ResetDailyIfNeeded();
   Print("=== ScalpMicro_10USD Initialized ===");
   Print("Symbol: ",_Symbol," | TF: ",EnumToString(InpTimeframe)," | Risk: ",InpRiskPercent,"% | Balance: ",AccountInfoDouble(ACCOUNT_BALANCE));
   Print("Spread filter: ",InpMaxSpreadPoints," points | SL ATR x",InpATR_SL_Mult," TP x",InpATR_TP_Mult);
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Deinit                                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   IndicatorRelease(handleEMA_Fast);
   IndicatorRelease(handleEMA_Slow);
   IndicatorRelease(handleRSI);
   IndicatorRelease(handleATR);
  }
//+------------------------------------------------------------------+
//| Reset daily counters                                             |
//+------------------------------------------------------------------+
void ResetDailyIfNeeded()
  {
   datetime now = TimeCurrent();
   MqlDateTime dt; TimeToStruct(now, dt);
   datetime today = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));
   if(today != dailyStartDay)
     {
      dailyStartDay = today;
      dailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      tradesToday = 0;
      // consecutiveLosses persists across days unless reset manually, but we keep it
      Print("New trading day. Start balance: ",dailyStartBalance);
     }
  }
//+------------------------------------------------------------------+
//| Count today's history deals                                      |
//+------------------------------------------------------------------+
void UpdateDailyStats()
  {
   ResetDailyIfNeeded();
   // Count trades today via history
   tradesToday = 0;
   HistorySelect(dailyStartDay, TimeCurrent());
   int total = HistoryDealsTotal();
   double dailyPL = 0;
   for(int i=0;i<total;i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket==0) continue;
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      string sym = HistoryDealGetString(ticket, DEAL_SYMBOL);
      if(magic != InpMagic) continue;
      if(sym != _Symbol) continue;
      ENUM_DEAL_TYPE type = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(type==DEAL_TYPE_BALANCE) continue;
      // only count entry deals? We'll count all
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);
      dailyPL += profit;
      // swap and commission
      dailyPL += HistoryDealGetDouble(ticket, DEAL_SWAP);
      dailyPL += HistoryDealGetDouble(ticket, DEAL_COMMISSION);
     }
   // Update consecutive losses from last deals
   consecutiveLosses = 0;
   for(int i=total-1; i>=0 && i>total-20; i--)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket==0) continue;
      if(HistoryDealGetInteger(ticket, DEAL_MAGIC)!=InpMagic) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL)!=_Symbol) continue;
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);
      if(entry != DEAL_ENTRY_OUT) continue; // only exits have PL
      double p = HistoryDealGetDouble(ticket, DEAL_PROFIT) + HistoryDealGetDouble(ticket, DEAL_SWAP) + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      if(p < 0) consecutiveLosses++;
      else break;
     }

   // Daily PL check
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   // Use equity for live monitoring
  }
//+------------------------------------------------------------------+
//| Check trading allowed                                            |
//+------------------------------------------------------------------+
bool IsTradingAllowed(string &reason)
  {
   ResetDailyIfNeeded();
   UpdateDailyStats();

   // Cooldown
   if(TimeCurrent() < coolDownUntil)
     {
      reason = StringFormat("Cooldown until %s", TimeToString(coolDownUntil));
      return false;
     }

   // Consecutive losses
   if(consecutiveLosses >= InpMaxConsecutiveLoss)
     {
      // if we haven't set cooldown, set it now
      if(coolDownUntil < TimeCurrent())
        {
         coolDownUntil = TimeCurrent() + InpCoolDownMinutes*60;
         Print("Loss streak ",consecutiveLosses," -> cooldown ",InpCoolDownMinutes," min");
        }
      reason = "Loss streak cooldown";
      return false;
     }

   // Daily loss / target
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   // Use equity vs dailyStartBalance
   double dailyPL = equity - dailyStartBalance;
   double dailyPLpct = (dailyStartBalance>0) ? (dailyPL/dailyStartBalance*100.0) : 0;

   if(dailyPLpct <= -InpMaxDailyLossPct)
     {
      reason = StringFormat("Daily loss limit hit %.2f%% (%.2f USD)", dailyPLpct, dailyPL);
      return false;
     }
   if(dailyPLpct >= InpDailyTargetPct)
     {
      reason = StringFormat("Daily target hit %.2f%% - locking profit", dailyPLpct);
      return false;
     }

   // Max trades per day
   if(tradesToday >= InpMaxTradesPerDay)
     {
      // recount via history
      HistorySelect(dailyStartDay, TimeCurrent());
      int cnt=0;
      for(int i=0;i<HistoryDealsTotal();i++)
        {
         ulong t=HistoryDealGetTicket(i);
         if(t==0) continue;
         if(HistoryDealGetInteger(t, DEAL_MAGIC)!=InpMagic) continue;
         if(HistoryDealGetString(t, DEAL_SYMBOL)!=_Symbol) continue;
         ENUM_DEAL_ENTRY e=(ENUM_DEAL_ENTRY)HistoryDealGetInteger(t, DEAL_ENTRY);
         if(e==DEAL_ENTRY_IN) cnt++;
        }
      tradesToday=cnt;
      if(tradesToday >= InpMaxTradesPerDay)
        {
         reason = "Max trades per day reached";
         return false;
        }
     }

   // Time filters
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if(!InpTradeMonday && dt.day_of_week==1) { reason="Monday disabled"; return false; }
   if(!InpTradeFriday && dt.day_of_week==5) { reason="Friday disabled"; return false; }
   if(dt.hour < InpStartHour || dt.hour > InpEndHour) { reason="Outside trading hours"; return false; }

   // Spread filter
   if(InpUseSpreadFilter)
     {
      long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPoints)
        {
         reason = StringFormat("Spread too high %d > %d", (int)spread, InpMaxSpreadPoints);
         return false;
        }
     }

   // Min bars between trades
   if(lastTradeTime>0 && TimeCurrent() - lastTradeTime < InpMinBarsBetweenTrades * PeriodSeconds(InpTimeframe))
     {
      reason="Too soon after last trade";
      return false;
     }

   // Margin check - $10 account critical
   double equityCheck = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equityCheck < 5.0)
     {
      reason="Equity too low (< $5) - stop to avoid margin call";
      return false;
     }

   // Check if we already have a position for this symbol+magic
   if(PositionSelect(_Symbol))
     {
      long posMagic = PositionGetInteger(POSITION_MAGIC);
      if(posMagic==InpMagic)
        {
         reason="Already in position";
         return false;
        }
     }

   reason="OK";
   return true;
  }
//+------------------------------------------------------------------+
//| Calculate lot size with risk %                                   |
//+------------------------------------------------------------------+
double CalculateLots(double sl_points)
  {
   if(sl_points <= 0) return InpFixedLot;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;

   // For $10 account, cap riskMoney min $0.15 to allow 0.01 lot
   // but never risk more than $0.50 per trade on $10
   if(balance <= 15.0)
     {
      riskMoney = MathMin(riskMoney, 0.40); // max $0.40 risk on tiny account
      riskMoney = MathMax(riskMoney, 0.10); // at least 10c to allow trade
     }

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(tickValue==0 || tickSize==0 || point==0) return InpFixedLot;

   double sl_money_per_lot = (sl_points * point / tickSize) * tickValue;
   if(sl_money_per_lot <= 0) return InpFixedLot;

   double lots = riskMoney / sl_money_per_lot;

   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   lots = MathFloor(lots / volStep) * volStep;
   lots = MathMax(lots, volMin);
   lots = MathMin(lots, volMax);
   lots = MathMin(lots, InpMaxLot); // hard cap for $10

   // Extra safety: for $10, never exceed 0.02 unless balance > $20
   if(balance < 20 && lots > 0.02) lots = 0.02;
   if(balance < 12 && lots > 0.01) lots = 0.01;

   // Normalize
   int digits = (int)MathLog10(1/volStep);
   lots = NormalizeDouble(lots, digits);

   return lots;
  }
//+------------------------------------------------------------------+
//| Signal logic                                                     |
//+------------------------------------------------------------------+
int GetSignal(double &sl_points, double &tp_points)
  {
   double emaFast[3], emaSlow[3], rsi[2], atr[2];
   if(CopyBuffer(handleEMA_Fast,0,0,3,emaFast)!=3) return 0;
   if(CopyBuffer(handleEMA_Slow,0,0,3,emaSlow)!=3) return 0;
   if(CopyBuffer(handleRSI,0,0,2,rsi)!=2) return 0;
   if(CopyBuffer(handleATR,0,0,2,atr)!=2) return 0;

   ArraySetAsSeries(emaFast,true);
   ArraySetAsSeries(emaSlow,true);
   ArraySetAsSeries(rsi,true);
   ArraySetAsSeries(atr,true);

   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double atrPoints = atr[0]/point;

   // ATR filters
   if(atrPoints < InpMinATRPoints || atrPoints > InpMaxATRPoints) return 0;

   sl_points = atrPoints * InpATR_SL_Mult;
   tp_points = atrPoints * InpATR_TP_Mult;

   // Ensure at least 80 points SL for scalping (8 pips)
   // and not too large (600 points)
   sl_points = MathMax(sl_points, 80);
   sl_points = MathMin(sl_points, 600);
   tp_points = MathMax(tp_points, 60);
   tp_points = MathMin(tp_points, 500);

   bool emaBull = emaFast[0] > emaSlow[0] && emaFast[1] <= emaSlow[1] + point*5; // allow cross recently
   bool emaBear = emaFast[0] < emaSlow[0] && emaFast[1] >= emaSlow[1] - point*5;

   // Alternative: if not fresh cross, allow continuation if emaFast above/below and slope ok
   bool emaBullCont = emaFast[0] > emaSlow[0] && emaFast[0] > emaFast[1];
   bool emaBearCont = emaFast[0] < emaSlow[0] && emaFast[0] < emaFast[1];

   double closePrice = iClose(_Symbol, InpTimeframe, 0);

   // BUY SIGNAL
   // Need EMA bullish and RSI in buy zone and price above EMA slow
   if( (emaBull || emaBullCont) && rsi[0] >= InpRSI_BuyMin && rsi[0] <= InpRSI_BuyMax && closePrice > emaSlow[0])
     {
      // Additional filter: RSI rising
      if(rsi[0] > rsi[1] - 2) // allow slight dip
         return 1;
     }
   // SELL SIGNAL
   if( (emaBear || emaBearCont) && rsi[0] >= InpRSI_SellMin && rsi[0] <= InpRSI_SellMax && closePrice < emaSlow[0])
     {
      if(rsi[0] < rsi[1] + 2)
         return -1;
     }

   return 0;
  }
//+------------------------------------------------------------------+
//| Manage open position (breakeven, trailing, time exit)            |
//+------------------------------------------------------------------+
void ManagePosition()
  {
   if(!PositionSelect(_Symbol)) return;
   long magic = PositionGetInteger(POSITION_MAGIC);
   if(magic != InpMagic) return;

   double priceOpen = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl = PositionGetDouble(POSITION_SL);
   double tp = PositionGetDouble(POSITION_TP);
   long type = PositionGetInteger(POSITION_TYPE);
   double priceCurrent = PositionGetDouble(POSITION_PRICE_CURRENT);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   datetime timeOpen = (datetime)PositionGetInteger(POSITION_TIME);

   double profitPoints = 0;
   if(type==POSITION_TYPE_BUY) profitPoints = (priceCurrent - priceOpen)/point;
   else profitPoints = (priceOpen - priceCurrent)/point;

   // Breakeven
   if(InpUseBreakeven && profitPoints >= InpBreakevenTriggerPoints)
     {
      double newSL = 0;
      if(type==POSITION_TYPE_BUY) newSL = priceOpen + InpBreakevenPlusPoints*point;
      else newSL = priceOpen - InpBreakevenPlusPoints*point;

      bool needModify = false;
      if(type==POSITION_TYPE_BUY && (sl < newSL || sl==0)) needModify=true;
      if(type==POSITION_TYPE_SELL && (sl > newSL || sl==0)) needModify=true;

      if(needModify)
        {
         trade.PositionModify(_Symbol, newSL, tp);
         Print("Breakeven set to ",newSL);
        }
     }

   // Trailing
   if(InpUseTrailing && profitPoints >= InpTrailingStartPoints)
     {
      double newSL = sl;
      if(type==POSITION_TYPE_BUY)
        {
         double trail = priceCurrent - InpTrailingStepPoints*point;
         if(trail > sl) newSL = trail;
        }
      else
        {
         double trail = priceCurrent + InpTrailingStepPoints*point;
         if(trail < sl || sl==0) newSL = trail;
        }
      if(newSL != sl)
        {
         trade.PositionModify(_Symbol, newSL, tp);
        }
     }

   // Time exit
   if(InpMaxHoldMinutes > 0)
     {
      if(TimeCurrent() - timeOpen >= InpMaxHoldMinutes*60)
        {
         Print("Time exit after ",InpMaxHoldMinutes," min");
         trade.PositionClose(_Symbol);
        }
     }
  }
//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
  {
   // Manage existing position first
   ManagePosition();

   // Only trade on new bar to avoid repaint
   static datetime lastBarTime = 0;
   datetime curBarTime = iTime(_Symbol, InpTimeframe, 0);
   if(curBarTime == lastBarTime) return;
   lastBarTime = curBarTime;

   // Check trading allowed
   string reason;
   if(!IsTradingAllowed(reason))
     {
      // Print only occasionally to avoid spam
      static datetime lastPrint=0;
      if(TimeCurrent()-lastPrint > 300)
        {
         Print("Trading paused: ",reason);
         lastPrint=TimeCurrent();
        }
      return;
     }

   double sl_points, tp_points;
   int signal = GetSignal(sl_points, tp_points);
   if(signal==0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   double lots = CalculateLots(sl_points);
   if(lots < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
     {
      Print("Lot too small ",lots);
      return;
     }

   // Check margin
   double price = (signal==1) ? ask : bid;
   double margin;
   if(!OrderCalcMargin((signal==1)?ORDER_TYPE_BUY:ORDER_TYPE_SELL, _Symbol, lots, price, margin))
     {
      Print("OrderCalcMargin failed");
      return;
     }
   double freeMargin = AccountInfoDouble(ACCOUNT_FREEMARGIN);
   if(margin > freeMargin * 0.9)
     {
      Print("Not enough margin: need ",margin," free ",freeMargin);
      return;
     }

   double sl=0, tp=0;
   if(signal==1)
     {
      sl = ask - sl_points*point;
      tp = ask + tp_points*point;
      // Ensure SL/TP respects stops level
      int stops = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      if(ask - sl < stops*point) sl = ask - stops*point - 10*point;
      if(tp - ask < stops*point) tp = ask + stops*point + 10*point;

      if(trade.Buy(lots, _Symbol, ask, sl, tp, InpComment))
        {
         lastTradeTime = TimeCurrent();
         tradesToday++;
         Print(StringFormat("BUY %.2f lots SL %.1f pts TP %.1f pts | ATR %.0f", lots, sl_points, tp_points, sl_points/InpATR_SL_Mult));
        }
      else
        {
         Print("Buy failed: ",GetLastError()," ",trade.ResultRetcodeDescription());
        }
     }
   else if(signal==-1)
     {
      sl = bid + sl_points*point;
      tp = bid - tp_points*point;
      int stops = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
      if(sl - bid < stops*point) sl = bid + stops*point + 10*point;
      if(bid - tp < stops*point) tp = bid - stops*point - 10*point;

      if(trade.Sell(lots, _Symbol, bid, sl, tp, InpComment))
        {
         lastTradeTime = TimeCurrent();
         tradesToday++;
         Print(StringFormat("SELL %.2f lots SL %.1f pts TP %.1f pts", lots, sl_points, tp_points));
        }
      else
        {
         Print("Sell failed: ",GetLastError()," ",trade.ResultRetcodeDescription());
        }
     }
  }
//+------------------------------------------------------------------+
