import { motion } from "framer-motion"
import { Database, Folder, HardDrive } from "lucide-react"
import { Card } from "@/components/ui/card"

interface SourceOption {
    id: string
    name: string
    icon: React.ElementType
    description: string
    available: boolean
}

const sources: SourceOption[] = [
    {
        id: "postgres",
        name: "PostgreSQL",
        icon: Database,
        description: "Connect to existing Postgres database",
        available: true,
    },
    {
        id: "snowflake",
        name: "Snowflake",
        icon: Folder,
        description: "Connect to Snowflake data warehouse",
        available: false,
    },
    {
        id: "mysql",
        name: "MySQL",
        icon: HardDrive,
        description: "Connect to MySQL database",
        available: false,
    },
]

interface ConnectSourceProps {
    onSelect: (sourceId: string) => void
}

export function ConnectSource({ onSelect }: ConnectSourceProps) {
    return (
        <div className="space-y-6">
            <div className="text-center space-y-2">
                <h2 className="text-3xl font-bold tracking-tight">Connect Data Source</h2>
                <p className="text-muted-foreground">Select where your raw data lives.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl mx-auto">
                {sources.map((source, index) => (
                    <motion.div
                        key={source.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                    >
                        <Card
                            className={`p-6 cursor-pointer border-2 transition-all hover:bg-accent/50 ${!source.available ? "opacity-50 cursor-not-allowed" : "hover:border-primary"
                                }`}
                            onClick={() => source.available && onSelect(source.id)}
                        >
                            <div className="flex items-center gap-4">
                                <div className="p-3 rounded-lg bg-primary/10 text-primary">
                                    <source.icon className="w-6 h-6" />
                                </div>
                                <div>
                                    <h3 className="font-semibold">{source.name}</h3>
                                    <p className="text-sm text-muted-foreground">
                                        {source.description}
                                    </p>
                                </div>
                            </div>
                        </Card>
                    </motion.div>
                ))}
            </div>
        </div>
    )
}
