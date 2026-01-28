import { useCallback } from 'react'
import {
    ReactFlow,
    Background,
    Controls,
    useNodesState,
    useEdgesState,
    addEdge,
    type Connection,
    type Edge,
    type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { TableNode } from './TableNode'
import { ChatSidebar } from "@/components/chat/ChatSidebar"

// Define node types
const nodeTypes = {
    table: TableNode,
}

// Initial mock data for testing
const initialNodes: Node[] = [
    {
        id: 'users',
        type: 'table',
        position: { x: 100, y: 100 },
        data: {
            label: 'users',
            columns: [
                { name: 'id', type: 'integer', isPrimaryKey: true },
                { name: 'email', type: 'varchar' },
                { name: 'created_at', type: 'timestamp' },
            ],
        },
    },
    {
        id: 'orders',
        type: 'table',
        position: { x: 450, y: 100 },
        data: {
            label: 'orders',
            columns: [
                { name: 'id', type: 'integer', isPrimaryKey: true },
                { name: 'user_id', type: 'integer', isForeignKey: true },
                { name: 'total', type: 'numeric' },
            ],
        },
    },
]

const initialEdges: Edge[] = [
    { id: 'e1-2', source: 'users', target: 'orders' },
]

export function ModelingCanvas() {
    const [nodes, , onNodesChange] = useNodesState(initialNodes)
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    )

    const handleSendMessage = (text: string) => {
        console.log("User sent:", text)
        // TODO: Connect to backend
    }

    return (
        <div className="w-full h-full border rounded-lg bg-background shadow-inner flex overflow-hidden">
            <div className="flex-1 h-full relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    nodeTypes={nodeTypes}
                    fitView
                >
                    <Background />
                    <Controls />
                </ReactFlow>
            </div>
            <ChatSidebar onSendMessage={handleSendMessage} />
        </div>
    )
}
