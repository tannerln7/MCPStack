"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select";

export function ThemeSelect() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  return (
    <Field className="mt-3 px-2 md:mt-auto">
      <FieldLabel htmlFor="appearance">Appearance</FieldLabel>
      <NativeSelect
        id="appearance"
        value={mounted ? theme : "system"}
        onChange={(event) => setTheme(event.target.value)}
        disabled={!mounted}
      >
        <NativeSelectOption value="light">Light</NativeSelectOption>
        <NativeSelectOption value="dark">Dark</NativeSelectOption>
        <NativeSelectOption value="system">System</NativeSelectOption>
      </NativeSelect>
    </Field>
  );
}
