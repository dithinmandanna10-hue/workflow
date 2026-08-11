//+------------------------------------------------------------------+
//|                                          ScalpSpam_10USD.mq5     |
//|  $10 ULTRA-SPAM QUICK SCALPER for MT5 - TICK SPAM MODE            |
//|  Strategy: EMA 5/13 + RSI(7) + Bollinger + ATR micro + TICK ENTRY|
//|  Spam = 80-150 trades/day, 30sec-3min holds, 3-7 pip TP           |
//|  For EURUSD M1 / GBPUSD M1 / XAU M1 / Volatility 75 M1            |
//|  $10 SAFE caps still: 0.01-0.03 lot, daily -7%/+8%, 200 trades max|
//|  Author: Arena Workflow - MAX SPAM 2026-08-11                     |
//+------------------------------------------------------------------+
#property copyright "Arena Workflow - Spam Scalper $10"
#property link      "https://github.com/dithinmandanna10-hue/workflow"
#property version   "2.00 SPAM"
#property strict
#property description "ULTRA quick spam scalper for $10."
#property description "TICK entry, 30sec-3min, spam 80-150/day, micro TP"
#property description "USE M1 CHART, Algo ON, spread filter strict!"

#include <Trade/Trade.mqh>
CTrade trade;

//--- INPUTS SPAM
input group "=== RISK $10 SPAM (HARD CAPS) ==="
input double   InpRiskPercent       = 1.8;      // Risk per spam trade % (1.5-2.5)
input double   InpFixedLot          = 0.01;     // Fixed lot micro (0.01)
input double   InpMaxLot            = 0.03;     // MAX lot spam cap 0.03 for $10
input double   InpMaxDailyLossPct   = 7.0;      // Spam daily loss stop 7%
input double   InpDailyTargetPct    = 8.0;      // Spam daily target 8% then lock
input int      InpMaxTradesPerDay   = 150;      // SPAM 150 trades/day max
input int      InpMaxConsecutiveLoss= 5;        // Spam pause after 5 losses
input int      InpCoolDownMinutes   = 10;       // Spam cooldown only 10 min

input group "=== SPAM STRATEGY M1 ==="
input ENUM_TIMEFRAMES InpTimeframe  = PERIOD_M1;// SPAM timeframe M1 ONLY
input int      InpEMAFast           = 5;        // EMA Fast 5
input int      InpEMASlow           = 13;       // EMA Slow 13
input int      InpRSIPeriod         = 7;        // RSI 7 ultra fast
input double   InpRSI_BuyMin        = 55.0;     // RSI buy >55
input double   InpRSI_BuyMax        = 78.0;     // RSI buy <78
input double   InpRSI_SellMin       = 22.0;     // RSI sell >22
input double   InpRSI_SellMax       = 45.0;     // RSI sell <45
input int      InpATRPeriod         = 10;       // ATR 10
input double   InpATR_SL_Mult       = 1.0;      // SL 1.0× ATR = 30-80 pts spam
input double   InpATR_TP_Mult       = 0.7;      // TP 0.7× ATR = 20-60 pts spam
input double   InpMinATRPoints      = 30;       // Min 30 pts (3 pips) spam
input double   InpMaxATRPoints      = 400;      // Max 400 pts spam filter
input int      InpBBPeriod          = 20;       // Bollinger 20
input double   InpBBDev             = 2.0;      // BB dev 2.0
input bool     InpUseBBFilter       = true;     // Filter with BB

input group "=== SPAM EXECUTION ==="
input bool     InpSpamMode          = true;     // TRUE = TICK spam, FALSE = new bar only
input int      InpMaxSpreadPoints   = 18;       // SPAM spread 18 pts EURUSD (strict)
input bool     InpUseSpreadFilter   = true;
input int      InpStartHour         = 7;        // London 07-22 spam
input int      InpEndHour           = 22;
input int      InpMinBarsBetweenTrades = 0;     // SPAM 0 bars = every tick
input int      InpMinSecondsBetweenTrades = 15; // SPAM 15 sec between orders
input bool     InpAllowHedging      = false;    // false = one position per symbol

input group "=== SPAM EXIT 30sec-3min ==="
input bool     InpUseBreakeven      = true;
input double   InpBreakevenPlusPoints= 20;      // Spam BE +20 pts lock
input double   InpBreakevenTriggerPoints= 35;   // Spam BE at +35 pts
input bool     InpUseTrailing       = true;
input double   InpTrailingStartPoints= 40;      // Spam trail 40 pts
input double   InpTrailingStepPoints = 15;      // Spam trail step 15 pts
input int      InpMaxHoldMinutes    = 3;        // SPAM max 3 min hold
input int      InpMaxHoldSeconds    = 180;      // 180 sec

input group "=== SYSTEM ==="
input long     InpMagic             = 202510;   // Magic SPAM
input string   InpComment           = "SPAM10$"; //

//--- GLOBALS
int handleEMA_Fast, handleEMA_Slow, handleRSI, handleATR, handleBB;
double dailyStartBalance=0; datetime dailyStartDay=0;
int tradesToday=0; int consecutiveLosses=0;
datetime coolDownUntil=0; datetime lastTradeTime=0;
double lastAsk=0, lastBid=0;

//+------------------------------------------------------------------+
//| Init                                                             |
//+------------------------------------------------------------------+
int OnInit()
  {
   handleEMA_Fast=iMA(_Symbol,InpTimeframe,InpEMAFast,0,MODE_EMA,PRICE_CLOSE);
   handleEMA_Slow=iMA(_Symbol,InpTimeframe,InpEMASlow,0,MODE_EMA,PRICE_CLOSE);
   handleRSI=iRSI(_Symbol,InpTimeframe,InpRSIPeriod,PRICE_CLOSE);
   handleATR=iATR(_Symbol,InpTimeframe,InpATRPeriod);
   handleBB=iBands(_Symbol,InpTimeframe,InpBBPeriod,0,InpBBDev,PRICE_CLOSE);
   if(handleEMA_Fast==INVALID_HANDLE||handleEMA_Slow==INVALID_HANDLE||handleRSI==INVALID_HANDLE||handleATR==INVALID_HANDLE||handleBB==INVALID_HANDLE)
     {Print("Handles failed"); return(INIT_FAILED);}
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   ResetDaily();
   Print("=== SPAM $10 ULTRA SCALPER READY ===");
   Print("SPAM Mode: ",InpSpamMode ? "TICK SPAM (every tick)" : "BAR");
   Print("Symbol ",_Symbol," M1 EMA",InpEMAFast,"/",InpEMASlow," RSI",InpRSIPeriod," ATR ",InpATR_SL_Mult,"/",InpATR_TP_Mult," Risk ",InpRiskPercent,"%");
   return(INIT_SUCCEEDED);
  }
void OnDeinit(const int r)
  {
   IndicatorRelease(handleEMA_Fast); IndicatorRelease(handleEMA_Slow);
   IndicatorRelease(handleRSI); IndicatorRelease(handleATR); IndicatorRelease(handleBB);
  }
//+------------------------------------------------------------------+
void ResetDaily()
  {
   datetime now=TimeCurrent(); MqlDateTime dt; TimeToStruct(now,dt);
   datetime today=StringToTime(StringFormat("%04d.%02d.%02d 00:00",dt.year,dt.mon,dt.day));
   if(today!=dailyStartDay){dailyStartDay=today; dailyStartBalance=AccountInfoDouble(ACCOUNT_BALANCE); tradesToday=0; Print("SPAM New day balance $",dailyStartBalance);}
  }
void UpdateStats()
  {
   ResetDaily();
   consecutiveLosses=0;
   HistorySelect(dailyStartDay,TimeCurrent());
   int total=HistoryDealsTotal(); int cnt=0;
   for(int i=total-1;i>=0 && i> total-30;i--)
     {
      ulong t=HistoryDealGetTicket(i); if(t==0) continue;
      if(HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagic) continue;
      if(HistoryDealGetString(t,DEAL_SYMBOL)!=_Symbol) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(t,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
      double p=HistoryDealGetDouble(t,DEAL_PROFIT)+HistoryDealGetDouble(t,DEAL_SWAP)+HistoryDealGetDouble(t,DEAL_COMMISSION);
      if(p<0) consecutiveLosses++; else break;
     }
   cnt=0; for(int i=0;i<total;i++){ulong t=HistoryDealGetTicket(i); if(t==0) continue; if(HistoryDealGetInteger(t,DEAL_MAGIC)!=InpMagic) continue; if(HistoryDealGetString(t,DEAL_SYMBOL)!=_Symbol) continue; if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(t,DEAL_ENTRY)==DEAL_ENTRY_IN) cnt++;}
   tradesToday=cnt;
  }
bool IsAllowed(string &reason)
  {
   ResetDaily(); UpdateStats();
   if(TimeCurrent()<coolDownUntil){reason=StringFormat("SPAM cooldown %s",TimeToString(coolDownUntil)); return false;}
   if(consecutiveLosses>=InpMaxConsecutiveLoss){coolDownUntil=TimeCurrent()+InpCoolDownMinutes*60; Print("SPAM 5-loss cooldown 10min"); reason="Loss streak 5"; return false;}
   double bal=AccountInfoDouble(ACCOUNT_BALANCE); double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double dpl=eq-dailyStartBalance; double pct=dailyStartBalance>0? dpl/dailyStartBalance*100:0;
   if(pct <= -InpMaxDailyLossPct){reason=StringFormat("SPAM daily loss %.2f%%",pct); return false;}
   if(pct >= InpDailyTargetPct){reason=StringFormat("SPAM daily target %.2f%% lock",pct); return false;}
   if(tradesToday>=InpMaxTradesPerDay){reason="SPAM max 150 trades"; return false;}
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   if(dt.hour < InpStartHour || dt.hour > InpEndHour){reason="Outside 07-22"; return false;}
   if(InpUseSpreadFilter){ long sp=SymbolInfoInteger(_Symbol,SYMBOL_SPREAD); if(sp > InpMaxSpreadPoints){reason=StringFormat("Spread %d > %d", (int)sp, InpMaxSpreadPoints); return false;}}
   if(eq < 4.0){reason="Equity < $4 SPAM stop"; return false;}
   if(lastTradeTime>0 && TimeCurrent()-lastTradeTime < InpMinSecondsBetweenTrades){reason=StringFormat("SPAM %ds gap", InpMinSecondsBetweenTrades); return false;}
   if(InpAllowHedging==false && PositionSelect(_Symbol) && PositionGetInteger(POSITION_MAGIC)==InpMagic){reason="SPAM already in pos"; return false;}
   reason="OK"; return true;
  }
double CalcLots(double sl_pts)
  {
   if(sl_pts<=0) return InpFixedLot;
   double bal=AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney=bal*InpRiskPercent/100.0;
   if(bal<=15){ riskMoney=MathMin(riskMoney,0.30); riskMoney=MathMax(riskMoney,0.10); }
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   double pt=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   if(tv==0||ts==0||pt==0) return InpFixedLot;
   double perLot=(sl_pts*pt/ts)*tv; if(perLot<=0) return InpFixedLot;
   double lots=riskMoney/perLot;
   double vMin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vMax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double vStep=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   lots=MathFloor(lots/vStep)*vStep;
   lots=MathMax(lots,vMin); lots=MathMin(lots,vMax); lots=MathMin(lots,InpMaxLot);
   if(bal<12 && lots>0.01) lots=0.01;
   else if(bal<25 && lots>0.02) lots=0.02;
   return NormalizeDouble(lots,2);
  }
int GetSpamSignal(double &sl_pts,double &tp_pts)
  {
   double ef[3],es[3],rsi[2],atr[2],bb_up[2],bb_lo[2],bb_mid[2];
   if(CopyBuffer(handleEMA_Fast,0,0,3,ef)!=3) return 0;
   if(CopyBuffer(handleEMA_Slow,0,0,3,es)!=3) return 0;
   if(CopyBuffer(handleRSI,0,0,2,rsi)!=2) return 0;
   if(CopyBuffer(handleATR,0,0,2,atr)!=2) return 0;
   if(CopyBuffer(handleBB,0,0,2,bb_mid)!=2) return 0;
   if(CopyBuffer(handleBB,1,0,2,bb_up)!=2) return 0;
   if(CopyBuffer(handleBB,2,0,2,bb_lo)!=2) return 0;
   ArraySetAsSeries(ef,true); ArraySetAsSeries(es,true); ArraySetAsSeries(rsi,true); ArraySetAsSeries(atr,true);
   ArraySetAsSeries(bb_up,true); ArraySetAsSeries(bb_lo,true);
   double pt=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double ap=atr[0]/pt; if(ap<InpMinATRPoints || ap> InpMaxATRPoints) return 0;
   sl_pts=ap*InpATR_SL_Mult; tp_pts=ap*InpATR_TP_Mult;
   sl_pts=MathMax(sl_pts,30); sl_pts=MathMin(sl_pts,300);
   tp_pts=MathMax(tp_pts,20); tp_pts=MathMin(tp_pts,200);
   bool bull=ef[0]>es[0] && ef[1]<=es[1]+pt*3; // fresh cross
   bool bear=ef[0]<es[0] && ef[1]>=es[1]-pt*3;
   bool bullCont=ef[0]>es[0] && ef[0]>ef[1] && rsi[0]>55;
   bool bearCont=ef[0]<es[0] && ef[0]<ef[1] && rsi[0]<45;
   double close=iClose(_Symbol,InpTimeframe,0);
   double bbW=bb_up[0]-bb_lo[0];
   bool bbOk=true; if(InpUseBBFilter) bbOk=bbW/pt > 30; // not squeeze

   // SPAM BUY: EMA bull + RSI 55-78 + close > emaSlow + not at upper BB
   if(bbOk && (bull||bullCont) && rsi[0]>=InpRSI_BuyMin && rsi[0]<=InpRSI_BuyMax && close>es[0] && close < bb_up[0]-pt*10)
     return 1;
   if(bbOk && (bear||bearCont) && rsi[0]>=InpRSI_SellMin && rsi[0]<=InpRSI_SellMax && close<es[0] && close > bb_lo[0]+pt*10)
     return -1;
   return 0;
  }
void ManageSpamPos()
  {
   if(!PositionSelect(_Symbol)) return;
   if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) return;
   double open=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL);
   double tp=PositionGetDouble(POSITION_TP);
   long type=PositionGetInteger(POSITION_TYPE);
   double cur=PositionGetDouble(POSITION_PRICE_CURRENT);
   double pt=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   datetime tOpen=(datetime)PositionGetInteger(POSITION_TIME);
   double pp=0; if(type==POSITION_TYPE_BUY) pp=(cur-open)/pt; else pp=(open-cur)/pt;
   if(InpUseBreakeven && pp>=InpBreakevenTriggerPoints)
     {
      double nsl=0; if(type==POSITION_TYPE_BUY) nsl=open+InpBreakevenPlusPoints*pt; else nsl=open-InpBreakevenPlusPoints*pt;
      bool need=false; if(type==POSITION_TYPE_BUY && (sl<nsl||sl==0)) need=true; if(type==POSITION_TYPE_SELL && (sl>nsl||sl==0)) need=true;
      if(need) trade.PositionModify(_Symbol,nsl,tp);
     }
   if(InpUseTrailing && pp>=InpTrailingStartPoints)
     {
      double nsl=sl;
      if(type==POSITION_TYPE_BUY){ double tr=cur-InpTrailingStepPoints*pt; if(tr>sl) nsl=tr; }
      else { double tr=cur+InpTrailingStepPoints*pt; if(tr<sl||sl==0) nsl=tr; }
      if(nsl!=sl) trade.PositionModify(_Symbol,nsl,tp);
     }
   if(InpMaxHoldSeconds>0 && TimeCurrent()-tOpen >= InpMaxHoldSeconds)
     { Print("SPAM time 180s close"); trade.PositionClose(_Symbol); }
  }
//+------------------------------------------------------------------+
void OnTick()
  {
   ManageSpamPos();
   // SPAM MODE: trade every tick, else only new bar
   static datetime lastBar=0;
   datetime curBar=iTime(_Symbol,InpTimeframe,0);
   if(!InpSpamMode)
     {
      if(curBar==lastBar) return;
      lastBar=curBar;
     }
   else
     {
      // in spam mode still respect 15 sec gap via IsAllowed, but allow tick
      // optional: still throttle to not spam same bar tick too much - we use seconds gap
     }
   string reason; if(!IsAllowed(reason))
     {
      static datetime lastP=0; if(TimeCurrent()-lastP>120){ Print("SPAM pause: ",reason); lastP=TimeCurrent();}
      return;
     }
   double slp, tpp; int sig=GetSpamSignal(slp,tpp); if(sig==0) return;
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double pt=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
   double lots=CalcLots(slp);
   if(lots < SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN)) return;
   double price=sig==1? ask: bid;
   double margin; if(!OrderCalcMargin(sig==1?ORDER_TYPE_BUY:ORDER_TYPE_SELL,_Symbol,lots,price,margin)) return;
   if(margin > AccountInfoDouble(ACCOUNT_FREEMARGIN)*0.85){ Print("SPAM margin low"); return;}
   double sl=0,tp=0; int stops=(int)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL);
   if(sig==1){ sl=ask - slp*pt; tp=ask + tpp*pt; if(ask-sl < stops*pt) sl=ask - stops*pt -5*pt; if(tp-ask < stops*pt) tp=ask+stops*pt+5*pt; if(trade.Buy(lots,_Symbol,ask,sl,tp,InpComment)){ lastTradeTime=TimeCurrent(); tradesToday++; Print(StringFormat("SPAM BUY %.2f SL%.0f TP%.0f",lots,slp,tpp));}}
   else { sl=bid + slp*pt; tp=bid - tpp*pt; if(sl-bid < stops*pt) sl=bid+stops*pt+5*pt; if(bid-tp < stops*pt) tp=bid-stops*pt-5*pt; if(trade.Sell(lots,_Symbol,bid,sl,tp,InpComment)){ lastTradeTime=TimeCurrent(); tradesToday++; Print(StringFormat("SPAM SELL %.2f SL%.0f TP%.0f",lots,slp,tpp));}}
  }
//+------------------------------------------------------------------+
