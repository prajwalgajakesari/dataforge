import { Handle, Position } from "@xyflow/react"
import { Database, Key } from "lucide-react"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

export interface Column {
    name: string
    type: string
    isPrimaryKey?: boolean
    isForeignKey?: boolean
}

export interface TableNodeData {
    label: string
    columns: Column[]
}

export function TableNode({ data }: { data: TableNodeData }) {
    return (
        <Card className="min-w-[250px] shadow-lg border-2 hover:border-primary/50 transition-colors">
            <CardHeader className="p-3 bg-muted/50 border-b">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Database className="w-4 h-4 text-primary" />
                    {data.label}
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                <div className="flex flex-col">
                    {data.columns.map((col, i) => (
                        <div
                            key={col.name}
                            className={`flex items-center justify-between px-3 py-2 text-xs hover:bg-muted/30 ${i !== data.columns.length - 1 ? "border-b" : ""
                                }`}
                        >
                            <div className="flex items-center gap-2">
                                {col.isPrimaryKey && <Key className="w-3 h-3 text-yellow-500" />}
                                <span className={col.isPrimaryKey ? "font-semibold" : ""}>
                                    {col.name}
                                </span>
                                {/* Connection handle for each column potentially */}
                                <Handle
                                    type="source"
                                    position={Position.Right}
                                    id={`${col.name}-source`}
                                    className="!bg-primary/50 !w-2 !h-2"
                                />
                                <Handle
                                    type="target"
                                    position={Position.Left}
                                    id={`${col.name}-target`}
                                    className="!bg-primary/50 !w-2 !h-2"
                                />
                            </div>
                            <span className="text-muted-foreground font-mono text-[10px]">
                                {col.type}
                            </span>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}
