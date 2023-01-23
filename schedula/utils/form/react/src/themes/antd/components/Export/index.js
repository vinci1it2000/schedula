import {Button} from 'antd';
import exportJSON from '../../../../core/utils/Export'

const Export = ({children, render, fileName, ...props}) => (
    <Button onClick={() => {
        exportJSON(render.formData, fileName || 'export.json')
    }} {...props}>
        {children || "Export"}
    </Button>
);

export default Export
