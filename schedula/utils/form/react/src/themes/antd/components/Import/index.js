import {Button} from 'antd';
import uploadJSON from '../../../../core/utils/Import'

const Import = ({children, render, fileName, ...props}) => (
    <Button {...props}>
        {children || "Import"}
        <input
            accept={['json']} type={'file'} hidden
            onChange={(event) => {
                uploadJSON(render.parent.props.onChange, event)
            }}/>
    </Button>
);

export default Import