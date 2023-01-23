import {Collapse} from 'antd';

const {Panel: BasePanel} = Collapse,
    Panel = ({children, render, ...props}) => (
        <BasePanel {...props}>
            {children}
        </BasePanel>);
export default Panel;