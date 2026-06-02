import { AlertTriangle, Gauge, RefreshCcw, TrendingUp, Waves } from "lucide-react-native";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { colors, radius, spacing, typography } from "../../theme/tokens";

type RiskBand = "LOW" | "MODERATE" | "CRITICAL";

type DashboardStatus = {
  district: string;
  district_index: number;
  current_flood_coverage_pct: number;
  historical_2010_baseline_pct: number;
  delta_severity_score: number;
  barrage_name: string;
  barrage_status: string;
  barrage_trend: string;
};

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const DEFAULT_DISTRICT = "Charsadda";

const FALLBACK_STATUS: DashboardStatus = {
  district: DEFAULT_DISTRICT,
  district_index: 5,
  current_flood_coverage_pct: 14.62,
  historical_2010_baseline_pct: 11.2,
  delta_severity_score: 3.42,
  barrage_name: "Tarbela Barrage",
  barrage_status: "EXTREME",
  barrage_trend: "Inflows Increasing"
};

function resolveRiskBand(index: number): RiskBand {
  if (index >= 7) return "CRITICAL";
  if (index >= 4) return "MODERATE";
  return "LOW";
}

function riskColor(band: RiskBand) {
  if (band === "CRITICAL") return colors.accentHigh;
  if (band === "MODERATE") return colors.accentWarning;
  return colors.accentSafe;
}

function metricPercent(value: number) {
  return `${value.toFixed(2)}%`;
}

function MetricCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <View style={styles.metricCard}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, accent ? { color: accent } : null]}>{value}</Text>
    </View>
  );
}

export function DashboardScreen() {
  const [status, setStatus] = useState<DashboardStatus>(FALLBACK_STATUS);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const riskBand = useMemo(() => resolveRiskBand(status.district_index), [status.district_index]);
  const riskAccent = useMemo(() => riskColor(riskBand), [riskBand]);
  const isDeltaPositive = status.delta_severity_score > 0;

  const loadDashboard = useCallback(async () => {
    setFetchError(null);
    try {
      const districtSlug = encodeURIComponent(status.district);
      const response = await fetch(`${API_BASE_URL}/api/status/${districtSlug}`);
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const payload = (await response.json()) as Partial<DashboardStatus>;
      setStatus((prev) => ({
        district: payload.district ?? prev.district,
        district_index: payload.district_index ?? prev.district_index,
        current_flood_coverage_pct: payload.current_flood_coverage_pct ?? prev.current_flood_coverage_pct,
        historical_2010_baseline_pct:
          payload.historical_2010_baseline_pct ?? prev.historical_2010_baseline_pct,
        delta_severity_score: payload.delta_severity_score ?? prev.delta_severity_score,
        barrage_name: payload.barrage_name ?? prev.barrage_name,
        barrage_status: payload.barrage_status ?? prev.barrage_status,
        barrage_trend: payload.barrage_trend ?? prev.barrage_trend
      }));
    } catch {
      setFetchError("Live status feed unavailable. Showing latest local telemetry snapshot.");
    }
  }, [status.district]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadDashboard();
    setIsRefreshing(false);
  }, [loadDashboard]);

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} tintColor={colors.accentInfo} />}
    >
      <Text style={styles.title}>District Hazard Dashboard</Text>
      <Text style={styles.subtitle}>{status.district} Tactical Command View</Text>

      <View style={[styles.card, styles.riskCard, { borderColor: riskAccent }]}>
        <View style={styles.rowTop}>
          <View style={styles.row}>
            <Gauge color={riskAccent} size={18} />
            <Text style={styles.label}>Unified Risk Indicator</Text>
          </View>
          <Text style={[styles.riskBand, { color: riskAccent }]}>{riskBand}</Text>
        </View>
        <Text style={[styles.riskValue, { color: riskAccent }]}>{status.district_index} / 10</Text>
      </View>

      <View style={styles.card}>
        <View style={styles.row}>
          <Waves color={colors.accentInfo} size={18} />
          <Text style={styles.label}>Comparative Inundation Matrix</Text>
        </View>
        <View style={styles.metricsGrid}>
          <MetricCard label="Current Flood Coverage %" value={metricPercent(status.current_flood_coverage_pct)} />
          <MetricCard
            label="2010 Historical Baseline %"
            value={metricPercent(status.historical_2010_baseline_pct)}
            accent={colors.textMuted}
          />
          <MetricCard
            label="Delta Severity Score"
            value={status.delta_severity_score.toFixed(2)}
            accent={isDeltaPositive ? colors.accentHigh : colors.accentSafe}
          />
        </View>
        {isDeltaPositive ? (
          <View style={styles.deltaAlert}>
            <TrendingUp color={colors.accentHigh} size={14} />
            <Text style={styles.deltaAlertText}>Current inundation exceeds 2010 historical baseline.</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.card}>
        <View style={styles.row}>
          <AlertTriangle color={colors.accentWarning} size={18} />
          <Text style={styles.label}>River Barrage Status Tracker</Text>
        </View>
        <Text style={styles.barrageValue}>
          {status.barrage_name} Status: <Text style={{ color: riskAccent }}>{status.barrage_status}</Text>
        </Text>
        <View style={styles.row}>
          <RefreshCcw color={colors.textMuted} size={14} />
          <Text style={styles.barrageSubtext}>{status.barrage_trend}</Text>
        </View>
      </View>

      {fetchError ? <Text style={styles.errorText}>{fetchError}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg
  },
  content: {
    backgroundColor: colors.bg,
    padding: spacing.xl,
    gap: spacing.md
  },
  title: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  subtitle: {
    color: colors.textMuted,
    fontFamily: typography.mono
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderColor: colors.border,
    borderWidth: 1,
    padding: spacing.md,
    gap: spacing.sm
  },
  riskCard: {
    borderWidth: 1.5
  },
  rowTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm
  },
  label: {
    color: colors.textMuted,
    fontFamily: typography.mono
  },
  riskBand: {
    fontFamily: typography.mono,
    fontWeight: "700"
  },
  riskValue: {
    color: colors.textPrimary,
    fontSize: 34,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  metricCard: {
    flexGrow: 1,
    flexBasis: "31%",
    minWidth: 140,
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.sm,
    gap: spacing.xs
  },
  metricLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontFamily: typography.mono
  },
  metricValue: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  deltaAlert: {
    marginTop: spacing.xs,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs
  },
  deltaAlertText: {
    color: colors.accentHigh,
    fontFamily: typography.mono
  },
  barrageValue: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  barrageSubtext: {
    color: colors.textMuted,
    fontFamily: typography.mono
  },
  errorText: {
    color: colors.accentWarning,
    fontFamily: typography.mono
  }
});
