import ExcelPreview from '../../components/ExcelPreview'

export default function ExcelPreviewWidget({value, options, ...props}) {
    return <ExcelPreview uri={value} {...options}/>
}