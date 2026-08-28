library("tidyverse")

dir.create("output", showWarnings = FALSE)

sectorNames <- c(XLB = "Materials", XLC = "Communication", XLE = "Energy",
                 XLF = "Financials", XLI = "Industrials", XLK = "Technology",
                 XLP = "Staples", XLRE = "Real Estate", XLU = "Utilities",
                 XLV = "Health Care", XLY = "Cons. Discretionary")

p1 <- allPerformanceModels %>%
  filter(term %in% c("Mkt_RF", "SMB", "HML")) %>%
  mutate(sector = sectorNames[ETF],
         term = factor(term, levels = c("Mkt_RF", "SMB", "HML"),
                       labels = c("Market beta", "Size (SMB)", "Value (HML)"))) %>%
  ggplot(aes(x = estimate, y = fct_reorder(sector, estimate), colour = term)) +
  geom_vline(xintercept = 0, colour = "grey60") +
  geom_pointrange(aes(xmin = estimate - 1.96 * std.error,
                      xmax = estimate + 1.96 * std.error),
                  position = position_dodge(width = 0.5)) +
  labs(title = "Fama-French factor loadings by sector",
       subtitle = "Monthly excess returns, 1998-2025; bars are 95% Newey-West intervals",
       x = "Coefficient", y = NULL, colour = NULL) +
  theme_minimal(base_size = 12) +
  theme(legend.position = "bottom")

ggsave("../output/factor_loadings.png", p1, width = 8, height = 6, dpi = 150)

macroTerms <- c(Inflation = "Inflation", interestRate = "Fed funds rate",
                govtSpending = "Federal spending", taxReceipts = "Customs receipts",
                adjustedBalance = "Trade balance", Tariff = "Tariff rate",
                Volatility = "VIX")

p2 <- bind_rows(monthly = allPerformanceModels,
                quarterly = quarterlyModels, .id = "frequency") %>%
  filter(term %in% names(macroTerms)) %>%
  mutate(sector = sectorNames[ETF],
         variable = macroTerms[term],
         label = if_else(p.value < 0.05, sprintf("%.1f", statistic), "")) %>%
  ggplot(aes(x = variable, y = sector, fill = statistic)) +
  geom_tile(colour = "white") +
  geom_text(aes(label = label), size = 3) +
  scale_fill_gradient2(low = "#b2182b", mid = "white", high = "#2166ac",
                       midpoint = 0, limits = c(-5, 5), oob = scales::squish) +
  facet_wrap(~ frequency) +
  labs(title = "Macro exposures by sector",
       subtitle = "Cell colour = Newey-West t-statistic; labelled where p < 0.05",
       x = NULL, y = NULL, fill = "t-stat") +
  theme_minimal(base_size = 11) +
  theme(axis.text.x = element_text(angle = 30, hjust = 1))

ggsave("../output/macro_heatmap.png", p2, width = 10, height = 6, dpi = 150)

p3 <- bind_rows(monthly = allPerformanceModels,
                quarterly = quarterlyModels, .id = "frequency") %>%
  filter(ETF == "XLE", term %in% names(macroTerms)) %>%
  mutate(variable = macroTerms[term]) %>%
  ggplot(aes(x = estimate, y = variable, colour = frequency)) +
  geom_vline(xintercept = 0, colour = "grey60") +
  geom_pointrange(aes(xmin = estimate - 1.96 * std.error,
                      xmax = estimate + 1.96 * std.error),
                  position = position_dodge(width = 0.5)) +
  facet_wrap(~ variable, scales = "free", ncol = 2) +
  labs(title = "Energy (XLE): macro coefficients at monthly and quarterly frequency",
       subtitle = "95% Newey-West intervals; inflation and spending effects hold at both",
       x = "Coefficient", y = NULL, colour = NULL) +
  theme_minimal(base_size = 11) +
  theme(legend.position = "bottom", axis.text.y = element_blank())

ggsave("../output/energy_robustness.png", p3, width = 9, height = 7, dpi = 150)