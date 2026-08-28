library(tidyverse) 
library(readxl)
library(sandwich)    
library(lmtest)
library(broom)

setwd(dirname(rstudioapi::getSourceEditorContext()$path))
filePath <- "../data/PURS Data.xlsx"


sheetNames <- excel_sheets(filePath)


# Read all sheets into a named list

allSheets <- sheetNames %>%
  set_names() %>% # Sets the names of the list elements to be the sheet names
  map(~ read_excel(path = filePath, sheet = .x))
cleanNames <- function(df) rename_with(df, ~ str_trim(str_replace_all(.x, "\u00a0", " ")))
allSheets  <- map(allSheets, cleanNames)

# Clean every table

cleanAllTables <- function() {
  cleanInflation <- allSheets$`Inflation rate` %>%
    mutate(
      Date = mdy(Date),
      Inflation = str_remove(Value, "%") %>%
        str_trim() %>%
        as.numeric() / 100
    )
  
  cleanTariffs <- allSheets$`Tariff rate` %>%
    mutate(Year = make_date(year = Year), Tariff = `Average Tariff`)
  
  cleanSpending <- allSheets$`Government Spending` %>% # Quarterly government spending
    mutate(Date = ymd(observation_date), Spending = FGEXPND)
  
  # Convert the numeric date to a proper R date
  cleanInterest <- read_excel(filePath, sheet = "Interest Rate", col_types = "text") %>%
    transmute(
      Date = if_else(
        str_detect(observation_date, "/"),
        mdy(observation_date),
        as.Date(as.numeric(observation_date), origin = "1899-12-30")
      ),
      interestRate = as.numeric(DFF) / 100
    )
  
  stopifnot(
    !any(is.na(cleanInterest$Date)),
    all(diff(cleanInterest$Date) > 0),
    min(cleanInterest$Date) == as.Date("1954-07-01")
  )
  
  cleanTradeBalance <- allSheets$`Trade Balance` %>%
    mutate(Date = ymd(observation_date), Balance = BOPGSTB)
  
  cleanCPI <- allSheets$`CPI Index` %>%
    mutate(Date = ymd(observation_date), CPI = CPIAUCSL)
  
  cleanVolatility <- allSheets$VIX %>%
    mutate(Date = mdy(Date), Volatility = Open)
  
  cleanTaxReceipts <- allSheets$`Quarterly Tariff Receipts` %>%
    mutate(Date = ymd(observation_date), taxReceipts = Receipt)
  
  cleanFamaFrench <- allSheets$`Fama French` %>%
    rename(date = 1) %>%
    mutate(Date = ymd(paste0(date, "01")),
           Mkt_RF = `Mkt-RF` / 100,
           SMB = SMB / 100,
           HML = HML / 100,
           RF = RF / 100) %>%
    select(Date, Mkt_RF, SMB, HML, RF)
  
  cleanTables <- list(
    inflation = cleanInflation,
    tariffs = cleanTariffs,
    govtSpending = cleanSpending,
    interest = cleanInterest,
    balance = cleanTradeBalance,
    CPI = cleanCPI,
    Volatility = cleanVolatility,
    taxReceipts = cleanTaxReceipts,
    famaFrench = cleanFamaFrench
  )
  
  return(cleanTables)
  
}

allCleanTables <- cleanAllTables()

# Model on explicative power of macroeconomic factors on industry ETFs

# Join and clean ETF with clean tables

finalizeTables <- function(ETF) {
  
  cleanTables <- allCleanTables
  
  cleanETF <- ETF %>% #Load ETF
    mutate(
      Date = mdy(Date),
      Price = as.numeric(`Adj Close`),        
      Year = make_date(year = year(Date))
    ) %>%
    select(Date, Price, Year)
  
  finalTable <- cleanETF %>% #Add Inflation and Tariffs
    left_join(y = cleanTables$CPI, by = "Date") %>%
    left_join(y = cleanTables$inflation, by = "Date") %>%
    left_join(y = cleanTables$tariffs, by = "Year") %>%
    left_join(y = cleanTables$govtSpending, by = "Date") %>%
    left_join(y = cleanTables$interest, by = "Date") %>%
    left_join(y = cleanTables$balance, by = "Date") %>%
    left_join(y = cleanTables$Volatility, by = "Date") %>%
    left_join(y = cleanTables$taxReceipts, by = "Date") %>%
    left_join(y = cleanTables$famaFrench, by = "Date") %>%
    
    # Arrange and fill NAs where there was no data to match based on the last obtained value.
    # For example, if there is an inflation value for November 1st, but not November 2nd, to use the November 1st value
    arrange(Date) %>%
    fill(CPI, .direction = "down") %>%
    fill(Tariff, .direction = "down") %>%
    fill(Inflation, .direction = "down") %>%
    fill(Spending, .direction = "down") %>%
    fill(interestRate, .direction = "down") %>%
    fill(Balance, .direction = "down") %>%
    fill(Volatility, .direction = "down") %>%
    fill(taxReceipts, .direction = "down")%>%
    fill(Mkt_RF, .direction = "down") %>%     
    fill(SMB, .direction = "down") %>%
    fill(HML, .direction = "down") %>%
    fill(RF, .direction = "down") %>%
      

      mutate(MonthID = floor_date(Date, "month")) %>% 
      group_by(MonthID) %>%                           
      filter(Date == max(Date)) %>%                   
      ungroup() %>%                                   
      select(-MonthID) %>%                           
      # ---------------------------------------------------------------
    
    mutate(
      latestCPI = last(CPI, na_rm = TRUE),
      adjustedPrice = Price * (latestCPI / CPI),
      Tariff = lag(Tariff, n = 0),
      govtSpending = Spending * (latestCPI / CPI),
      adjustedBalance = Balance * (latestCPI / CPI),
      taxReceipts = taxReceipts * (latestCPI / CPI)
    ) %>%
    select(
      Date,
      adjustedPrice,
      Inflation,
      Tariff,
      govtSpending,
      interestRate,
      adjustedBalance,
      taxReceipts,
      Volatility,
      Mkt_RF,
      SMB,
      HML, RF
    )
  return(finalTable)
}

# Collapse a monthly table (output of finalizeTables) to quarter-end rows
toQuarterly <- function(tbl) {
  tbl %>%
    mutate(Quarter = floor_date(Date, "quarter")) %>%
    group_by(Quarter) %>%
    summarise(
      Date            = last(Date),
      adjustedPrice   = last(adjustedPrice),      # quarter-end price
      Tariff          = last(Tariff),
      govtSpending    = last(govtSpending),
      interestRate    = last(interestRate),
      Inflation       = last(Inflation),
      adjustedBalance = last(adjustedBalance),
      taxReceipts     = last(taxReceipts),
      Volatility      = last(Volatility),
      Mkt_RF = expm1(sum(log1p(Mkt_RF))),         # compound the three monthly factor returns
      SMB    = expm1(sum(log1p(SMB))),
      HML    = expm1(sum(log1p(HML))),
      RF     = expm1(sum(log1p(RF))),
      nMonths = n(),
      .groups = "drop"
    ) %>%
    filter(nMonths == 3) %>%                      # drop partial quarters at the sample edges
    select(-Quarter, -nMonths)
}


# Function to model every ETF based on model function

modelEveryETF <- function(modelType, ETFs = c("XLC","XLY","XLP","XLE","XLF","XLV",
                                              "XLI","XLB","XLRE","XLK","XLU"), ...) {
  map_dfr(ETFs, function(etf) {
    modelType(allSheets[[etf]], ...) %>% mutate(ETF = etf, .before = 1)
  })
}

# Performance Model

createPerformanceModel <- function(ETF, freq = c("monthly", "quarterly")) {
  freq <- match.arg(freq)
  nwLag <- if (freq == "quarterly") 1 else 3
  tableForModel <- finalizeTables(ETF)
  if (freq == "quarterly") tableForModel <- toQuarterly(tableForModel)
  tableForModel <- tableForModel %>%
    mutate(
      adjustedPrice = calculateLogReturn(adjustedPrice, lag(adjustedPrice)) - RF,
      Tariff = calculateChange(Tariff, lag(Tariff)),
      govtSpending = calculateLogReturn(govtSpending, lag(govtSpending)),
      interestRate = calculateChange(interestRate, lag(interestRate)),
      adjustedBalance = calculateLogReturn(adjustedBalance, lag(adjustedBalance)),
      taxReceipts = calculateLogReturn(taxReceipts, lag(taxReceipts)),
      Volatility = calculateChange(Volatility, lag(Volatility)),
      Inflation = calculateChange(Inflation, lag(Inflation)))
  
  ETFModel <- launchModel(tableForModel)
  
  # Return summary of Models
  
  modelSummary <- summarizeModel(ETFModel, nwLag = nwLag)
  return(modelSummary)
}

calculateLogReturn <- function(currentPrice, oldPrice) {
  return(log(currentPrice / oldPrice))
}


# Formula to calculate absolute changes in factors

calculateChange <- function(currentPrice, oldPrice) {
  change = currentPrice - oldPrice
  return(change)
}

# Function to create models

launchModel <- function(table) {
  ETFModel <- lm(adjustedPrice ~ Tariff + govtSpending + interestRate + 
                   adjustedBalance + Volatility + taxReceipts + Inflation + Mkt_RF + SMB + HML,
                 table) # Linear model, 
  
  return(ETFModel)
}


# Function to summarize model

summarizeModel <- function(model, nwLag = 3) {
  ct <- coeftest(model, vcov = NeweyWest(model, lag = nwLag, prewhite = FALSE))
  tidy(ct) %>%                                  # term, estimate, std.error, statistic, p.value
    filter(term != "(Intercept)") %>%
    mutate(R2 = summary(model)$r.squared,
           n  = nobs(model))
}

# Long: one row per ETF x term. Filter to whatever you're looking at.
longTable <- function(models, whichTerm) {
  models %>%
    filter(term == whichTerm) %>%
    arrange(p.value)
}
# Wide: one row per ETF, like your old output
wideTable <- function(models) {
  models %>%
    select(ETF, R2, n, term, estimate, p.value) %>%
    pivot_wider(names_from = term, values_from = c(estimate, p.value)) %>%
    print(width = Inf)
}

allPerformanceModels <- modelEveryETF(createPerformanceModel)
# Filter term
longTable(allPerformanceModels, "interestRate")

wideTable(allPerformanceModels)

quarterlyModels <- modelEveryETF(createPerformanceModel,  ETFs = c("XLY","XLP","XLE","XLF","XLV","XLI","XLB","XLK","XLU"),
                                 freq = "quarterly")

longTable(quarterlyModels, "interestRate")

wideTable(quarterlyModels)

# --- One-off influence check on the quarterly Energy model ---
xleQ <- finalizeTables(allSheets$XLE) %>% toQuarterly() %>%
  mutate(
    adjustedPrice   = calculateLogReturn(adjustedPrice, lag(adjustedPrice)) - RF,
    Tariff          = calculateChange(Tariff, lag(Tariff)),
    govtSpending    = calculateLogReturn(govtSpending, lag(govtSpending)),
    interestRate    = calculateChange(interestRate, lag(interestRate)),
    adjustedBalance = calculateLogReturn(adjustedBalance, lag(adjustedBalance)),
    taxReceipts     = calculateLogReturn(taxReceipts, lag(taxReceipts)),
    Volatility      = calculateChange(Volatility, lag(Volatility)),
    Inflation       = calculateChange(Inflation, lag(Inflation))
  ) %>% drop_na()

xleModel <- launchModel(xleQ)

# Which quarters drive the fit?
xleQ %>%
  mutate(cooksD = cooks.distance(xleModel)) %>%
  select(Date, cooksD, adjustedPrice, govtSpending, taxReceipts, Inflation) %>%
  arrange(desc(cooksD)) %>%
  head(6)

# Same model with 2020 removed
xleNo2020 <- launchModel(filter(xleQ, year(Date) != 2020))
summarizeModel(xleNo2020, nwLag = 1) %>%
  filter(term %in% c("govtSpending", "taxReceipts", "Inflation"))

dir.create("../output", showWarnings = FALSE)
write_csv(wideTable(allPerformanceModels), "../output/monthly_results.csv")
write_csv(wideTable(quarterlyModels),      "../output/quarterly_results.csv")

source("plots.R")