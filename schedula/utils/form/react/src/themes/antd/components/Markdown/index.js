import ReactAntdown from 'react-antdown'
import formatMd from '../../../../core/utils/Markdown'
import remarkGfm from 'remark-gfm'

export default function Markdown({children, render, ...props}) {
    return <ReactAntdown
        remarkPlugins={[remarkGfm]}
        urlTransform={uri => uri}>
        {formatMd({
            children, formData: render.formData, ...props
        })}
    </ReactAntdown>
}