import {Image} from 'antd';

const {PreviewGroup: BasePreviewGroup} = Image,
    PreviewGroup = ({children, render, ...props}) => (
        <BasePreviewGroup {...props}>
            {children}
        </BasePreviewGroup>);
export default PreviewGroup;