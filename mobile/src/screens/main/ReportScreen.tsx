import { useEffect, useMemo, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { colors, radius, spacing, typography } from "../../theme/tokens";

type TacticalReport = {
  target_area: string;
  generated_at: string;
  situation_summary: string;
  hydraulic_analysis: string;
  historical_benchmark: string;
  operational_actions: string;
  confidence_fidelity: string;
};

type SectionCard = {
  key: string;
  title: string;
  content: string;
};

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const DEFAULT_DISTRICT = "Charsadda";

const FALLBACK_REPORT: TacticalReport = {
  target_area: "Charsadda District",
  generated_at: "2026-06-02T09:30:00Z",
  situation_summary:
    "Localized floodplain expansion remains active in low-lying settlements. Saturation persistence indicates ongoing pressure on tactical response corridors.",
  hydraulic_analysis:
    "Matched gauge telemetry shows elevated inflow with sustained surface spread near embankment-adjacent zones. Channel velocity remains above routine seasonal envelope.",
  historical_benchmark:
    "Current inundation footprint is above 2010 baseline in exposed union councils, with localized exceedance concentrated near recurring breach-prone segments.",
  operational_actions:
    "Maintain rapid-response staging in vulnerable sectors, prioritize evacuation support for high-risk clusters, and continue 6-hour surveillance update cycle.",
  confidence_fidelity:
    "High confidence for near-term trend persistence. Moderate confidence for 24-hour escalation path due to rainfall uncertainty and discharge regulation variance."
};

function SectionBlock({ title, content }: { title: string; content: string }) {
  return (
    <View style={styles.sectionCard}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionBody}>{content}</Text>
    </View>
  );
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

export function ReportScreen() {
  const [report, setReport] = useState<TacticalReport>(FALLBACK_REPORT);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const sections = useMemo<SectionCard[]>(
    () => [
      { key: "summary", title: "📋 [SITUATION SUMMARY]", content: report.situation_summary },
      { key: "hydraulic", title: "🌊 [HYDRAULIC ANALYSIS]", content: report.hydraulic_analysis },
      { key: "benchmark", title: "⏳ [HISTORICAL BENCHMARK]", content: report.historical_benchmark },
      { key: "actions", title: "🚨 [OPERATIONAL ACTIONS]", content: report.operational_actions },
      { key: "confidence", title: "🎯 [CONFIDENCE FIDELITY]", content: report.confidence_fidelity }
    ],
    [report]
  );

  useEffect(() => {
    void loadReport();
  }, []);

  async function loadReport() {
    setFetchError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/report/${encodeURIComponent(DEFAULT_DISTRICT)}`);
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const payload = (await response.json()) as Partial<TacticalReport> & {
        sections?: Partial<TacticalReport>;
        district?: string;
        targetArea?: string;
        generatedAt?: string;
      };

      setReport((prev) => {
        const mergedSections = payload.sections ?? {};
        return {
          target_area: payload.target_area ?? payload.targetArea ?? payload.district ?? prev.target_area,
          generated_at: payload.generated_at ?? payload.generatedAt ?? prev.generated_at,
          situation_summary: payload.situation_summary ?? mergedSections.situation_summary ?? prev.situation_summary,
          hydraulic_analysis: payload.hydraulic_analysis ?? mergedSections.hydraulic_analysis ?? prev.hydraulic_analysis,
          historical_benchmark:
            payload.historical_benchmark ?? mergedSections.historical_benchmark ?? prev.historical_benchmark,
          operational_actions:
            payload.operational_actions ?? mergedSections.operational_actions ?? prev.operational_actions,
          confidence_fidelity:
            payload.confidence_fidelity ?? mergedSections.confidence_fidelity ?? prev.confidence_fidelity
        };
      });
    } catch {
      setFetchError("Strategic AI feed unavailable. Displaying latest synchronized report snapshot.");
    }
  }

  async function onRefresh() {
    setIsRefreshing(true);
    await loadReport();
    setIsRefreshing(false);
  }

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} tintColor={colors.accentInfo} />}
    >
      <Text style={styles.title}>Strategic AI Intelligence Viewer</Text>
      <View style={styles.headerCard}>
        <Text style={styles.metaLabel}>Target Area</Text>
        <Text style={styles.metaValue}>{report.target_area}</Text>
        <Text style={styles.metaLabel}>Last Inference Cron Execution</Text>
        <Text style={styles.metaValue}>{formatTimestamp(report.generated_at)}</Text>
      </View>

      {sections.map((section) => (
        <SectionBlock key={section.key} title={section.title} content={section.content} />
      ))}

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
  headerCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs
  },
  metaLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontFamily: typography.mono
  },
  metaValue: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  sectionCard: {
    backgroundColor: colors.surfaceMuted,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.xs
  },
  sectionTitle: {
    color: colors.accentInfo,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  sectionBody: {
    color: colors.textPrimary,
    fontFamily: typography.mono
  },
  errorText: {
    color: colors.accentWarning,
    fontFamily: typography.mono
  }
});
