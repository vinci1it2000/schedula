import {Layout} from 'antd';

const {Content: BaseContent} = Layout,
    Content = ({children, render, ...props}) => (
        <BaseContent {...props}>
            {children}
        </BaseContent>);
export default Content;