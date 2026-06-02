import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { DISTRICTS, DistrictName } from "../../constants/districts";
import { AuthStackParamList } from "../../navigation/types";
import { colors, radius, spacing, typography } from "../../theme/tokens";

type Props = NativeStackScreenProps<AuthStackParamList, "Signup">;

export function SignupScreen({ navigation }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [district, setDistrict] = useState<DistrictName>("Charsadda");

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Create Account</Text>
      <TextInput
        style={styles.input}
        placeholder="Email"
        placeholderTextColor={colors.textMuted}
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor={colors.textMuted}
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      <TextInput
        style={styles.input}
        placeholder="Phone (+92...)"
        placeholderTextColor={colors.textMuted}
        keyboardType="phone-pad"
        value={phone}
        onChangeText={setPhone}
      />

      <Text style={styles.sectionLabel}>District Selection</Text>
      <View style={styles.pickerWrap}>
        {DISTRICTS.map((item) => (
          <Pressable
            key={item}
            style={[styles.pickerItem, item === district && styles.pickerItemActive]}
            onPress={() => setDistrict(item)}
          >
            <Text style={[styles.pickerText, item === district && styles.pickerTextActive]}>{item}</Text>
          </Pressable>
        ))}
      </View>

      <Pressable style={styles.primaryBtn} onPress={() => navigation.navigate("Otp", { phoneNumber: phone, district })}>
        <Text style={styles.primaryBtnText}>Continue to OTP</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg
  },
  content: {
    padding: spacing.xl,
    gap: spacing.md
  },
  heading: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontFamily: typography.mono
  },
  sectionLabel: {
    color: colors.textMuted,
    fontFamily: typography.mono
  },
  pickerWrap: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.sm,
    gap: spacing.xs
  },
  pickerItem: {
    padding: spacing.sm,
    borderRadius: radius.sm
  },
  pickerItemActive: {
    backgroundColor: colors.surfaceMuted
  },
  pickerText: {
    color: colors.textMuted,
    fontFamily: typography.mono
  },
  pickerTextActive: {
    color: colors.textPrimary
  },
  primaryBtn: {
    marginTop: spacing.sm,
    backgroundColor: colors.accentInfo,
    borderRadius: radius.md,
    alignItems: "center",
    paddingVertical: spacing.sm
  },
  primaryBtnText: {
    color: "#02131F",
    fontWeight: "700",
    fontFamily: typography.mono
  }
});
