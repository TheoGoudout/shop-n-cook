import { useQueries } from "@tanstack/react-query"
import { ChefHat, FlaskConical, ShoppingCart } from "lucide-react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import {
  IngredientsService,
  RecipesService,
  ShoppingListsService,
} from "@/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
]

const statsMeta = [
  { label: "Recipes", icon: ChefHat },
  { label: "Ingredients", icon: FlaskConical },
  { label: "Shopping Lists", icon: ShoppingCart },
]

export function StatsChart() {
  const results = useQueries({
    queries: [
      {
        queryKey: ["stats", "recipes"],
        queryFn: () => RecipesService.readRecipes({ limit: 1 }),
      },
      {
        queryKey: ["stats", "ingredients"],
        queryFn: () => IngredientsService.readIngredients({ limit: 1 }),
      },
      {
        queryKey: ["stats", "shopping-lists"],
        queryFn: () => ShoppingListsService.readShoppingLists({ limit: 1 }),
      },
    ],
  })

  const counts = results.map((r) => r.data?.count ?? 0)
  const isLoading = results.some((r) => r.isLoading)

  const chartData = statsMeta.map(({ label }, i) => ({
    name: label,
    value: counts[i],
  }))

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {statsMeta.map(({ label, icon: Icon }, i) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {label}
              </CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">
                {isLoading ? "—" : counts[i]}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Kitchen Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={chartData}
              margin={{ top: 4, right: 16, left: -16, bottom: 4 }}
              barSize={48}
            >
              <CartesianGrid
                vertical={false}
                strokeDasharray="3 3"
                className="stroke-border"
              />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 13, fill: "var(--color-muted-foreground)" }}
              />
              <YAxis
                allowDecimals={false}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 12, fill: "var(--color-muted-foreground)" }}
              />
              <Tooltip
                cursor={{ fill: "var(--color-muted)", opacity: 0.4 }}
                contentStyle={{
                  background: "var(--color-card)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  fontSize: 13,
                }}
                labelStyle={{
                  color: "var(--color-card-foreground)",
                  fontWeight: 600,
                }}
                itemStyle={{ color: "var(--color-muted-foreground)" }}
              />
              <Bar dataKey="value" name="Total" radius={[4, 4, 0, 0]}>
                {chartData.map((_entry, index) => (
                  <Cell
                    key={index}
                    fill={CHART_COLORS[index % CHART_COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}
