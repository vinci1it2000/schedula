import {Splitter} from 'antd';

const {Panel: BasePanel} = Splitter,
    Panel = ({children, render, ...props}) => (
        <BasePanel {...props}>
            {children}
        </BasePanel>);
export default Panel;