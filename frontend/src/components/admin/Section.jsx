import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function Section({ title, children, className }) {
  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
