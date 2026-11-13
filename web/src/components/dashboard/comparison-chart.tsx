'use client'

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from 'recharts'

import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import type { Axis, ChartRow } from '@/lib/results'
import { formatNumber } from '@/lib/results'

interface Props {
  rows: ChartRow[]
  axis: Axis
  unit: string
  labelA: string | null
  labelB: string | null
  digits: number
}

export function ComparisonChart({ rows, axis, unit, labelA, labelB, digits }: Props) {
  const config = {
    a: { label: labelA ?? 'Référence', color: 'var(--chart-5)' },
    b: { label: labelB ?? 'Variante', color: 'var(--chart-2)' },
  } satisfies ChartConfig
  const xUnit = axis === 'angle' ? '°' : 'ms'
  const maxX = rows.length ? rows[rows.length - 1].x : 0
  const ticks =
    axis === 'angle'
      ? Array.from({ length: Math.floor(maxX / 90) + 1 }, (_, index) => index * 90)
      : undefined

  return (
    <ChartContainer config={config} className="aspect-auto h-72 w-full">
      <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <CartesianGrid vertical={false} strokeDasharray="3 3" />
        <XAxis
          dataKey="x"
          type="number"
          domain={[0, 'dataMax']}
          ticks={ticks}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={(value: number) => `${formatNumber(value, 0)} ${xUnit}`}
        />
        <YAxis
          width={56}
          tickLine={false}
          axisLine={false}
          tickMargin={4}
          tickFormatter={(value: number) => formatNumber(value, digits)}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(_, payload) => {
                const x = (payload?.[0]?.payload as ChartRow | undefined)?.x ?? 0
                return `${formatNumber(x, axis === 'angle' ? 0 : 2)} ${xUnit}`
              }}
              formatter={(value, name) => (
                <div className="flex w-full items-center justify-between gap-4">
                  <span className="text-muted-foreground">{config[name as 'a' | 'b']?.label}</span>
                  <span className="tabular font-medium text-foreground">
                    {formatNumber(Number(value), digits + 1)} {unit}
                  </span>
                </div>
              )}
            />
          }
        />
        <ChartLegend content={<ChartLegendContent />} />
        {labelA && (
          <Line
            dataKey="a"
            type="monotone"
            stroke="var(--color-a)"
            strokeWidth={2}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        )}
        {labelB && (
          <Line
            dataKey="b"
            type="monotone"
            stroke="var(--color-b)"
            strokeWidth={2}
            strokeDasharray="6 4"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        )}
      </LineChart>
    </ChartContainer>
  )
}
