import { motion } from "framer-motion"
import { LayoutTemplate, Network, Share2 } from "lucide-react"
import { Card } from "@/components/ui/card"

interface StrategyOption {
    id: string
    name: string
    icon: React.ElementType
    description: string
    pros: string[]
}

const strategies: StrategyOption[] = [
    {
        id: "STAR_SCHEMA",
        name: "Star Schema",
        icon: LayoutTemplate,
        description: "Dimensional modeling for analytics & BI",
        pros: ["Best for BI tools", "Simple queries", "Fast aggregations"],
    },
    {
        id: "NORMALIZED_3NF",
        name: "Normalized (3NF)",
        icon: Share2,
        description: "Relational design to reduce redundancy",
        pros: ["Data integrity", "Flexible querying", "No redundancy"],
    },
    {
        id: "DATA_VAULT",
        name: "Data Vault 2.0",
        icon: Network,
        description: "Hubs, Links, and Satellites for enterprise scale",
        pros: ["Auditable history", "Scalable integration", "Resilient"],
    },
]

interface SelectStrategyProps {
    onSelect: (strategyId: string) => void
}

export function SelectStrategy({ onSelect }: SelectStrategyProps) {
    return (
        <div className="space-y-6">
            <div className="text-center space-y-2">
                <h2 className="text-3xl font-bold tracking-tight">Choose Modeling Strategy</h2>
                <p className="text-muted-foreground">How should we structure your data?</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mx-auto">
                {strategies.map((strategy, index) => (
                    <motion.div
                        key={strategy.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 + index * 0.1 }}
                    >
                        <Card
                            className="p-6 cursor-pointer border-2 transition-all hover:border-primary hover:scale-[1.02]"
                            onClick={() => onSelect(strategy.id)}
                        >
                            <div className="flex flex-col gap-4 h-full">
                                <div className="p-3 w-fit rounded-lg bg-primary/10 text-primary">
                                    <strategy.icon className="w-6 h-6" />
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-semibold text-lg">{strategy.name}</h3>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        {strategy.description}
                                    </p>
                                </div>
                                <div className="border-t pt-4 mt-2">
                                    <ul className="text-xs text-muted-foreground space-y-2">
                                        {strategy.pros.map((pro) => (
                                            <li key={pro} className="flex items-center gap-2">
                                                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                                                {pro}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </Card>
                    </motion.div>
                ))}
            </div>
        </div>
    )
}
