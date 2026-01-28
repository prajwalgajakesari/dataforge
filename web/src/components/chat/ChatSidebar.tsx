import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

interface Message {
    role: "user" | "assistant"
    content: string
}

interface ChatSidebarProps {
    onSendMessage: (message: string) => void
}

export function ChatSidebar({ onSendMessage }: ChatSidebarProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: "assistant",
            content: "Hi! I've analyzed your data. The current schema is a starting point. How would you like to refine it? You can ask me to rename tables, merge columns, or change the strategy.",
        },
    ])
    const [input, setInput] = useState("")
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [messages])

    const handleSend = () => {
        if (!input.trim()) return

        const newMsg: Message = { role: "user", content: input }
        setMessages((prev) => [...prev, newMsg])
        onSendMessage(input)
        setInput("")

        // Simulate generic AI response for now (backend integration later)
        setTimeout(() => {
            setMessages(prev => [...prev, { role: 'assistant', content: "I'm processing your request... generic response placeholder." }])
        }, 1000)
    }

    return (
        <div className="flex flex-col h-full border-l bg-background w-[350px]">
            <div className="p-4 border-b flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-primary" />
                <h3 className="font-semibold">DataForge Agent</h3>
            </div>

            <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                <div className="space-y-4">
                    {messages.map((msg, i) => (
                        <div
                            key={i}
                            className={cn(
                                "flex gap-3 text-sm",
                                msg.role === "user" ? "flex-row-reverse" : "flex-row"
                            )}
                        >
                            <div
                                className={cn(
                                    "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                                    msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                                )}
                            >
                                {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                            </div>
                            <div
                                className={cn(
                                    "p-3 rounded-lg max-w-[80%]",
                                    msg.role === "user"
                                        ? "bg-primary text-primary-foreground"
                                        : "bg-muted text-foreground"
                                )}
                            >
                                {msg.content}
                            </div>
                        </div>
                    ))}
                </div>
            </ScrollArea>

            <div className="p-4 border-t">
                <div className="flex gap-2">
                    <input
                        className="flex-1 bg-background border rounded-md px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                        placeholder="Ask me to change something..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSend()}
                    />
                    <Button size="icon" onClick={handleSend} disabled={!input.trim()}>
                        <Send className="w-4 h-4" />
                    </Button>
                </div>
            </div>
        </div>
    )
}
