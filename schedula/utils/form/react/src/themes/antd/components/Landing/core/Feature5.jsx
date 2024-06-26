import React from 'react';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import {Tabs, Row, Col} from 'antd';
import Icon from '@ant-design/icons';
import {getChildrenToRender} from './utils';

const TabPane = Tabs.TabPane;

class Content7 extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            current: 1,
        };
    }

    onChange = (key) => {
        this.setState({current: parseFloat(key)});
    };

    getBlockChildren = (item, i) => {
        const {tag, content} = item;
        const {text, img} = content;
        const textChildren = text.children;
        const {icon} = tag;
        const iconChildren = icon.children;
        const tagText = tag.text;
        return (
            <TabPane
                key={i + 1}
                tab={
                    <div className={tag.className}>
                        <Icon type={iconChildren} className={icon.className}/>
                        <div {...tagText}>{tagText.children}</div>
                    </div>
                }
                className={item.className}
            >
                {this.state.current === i + 1 && (
                    <Row
                        key="content"
                        className={content.className}
                        gutter={content.gutter}
                    >
                        <Col className={text.className} xs={text.xs}
                             md={text.md}>
                            {textChildren}
                        </Col>
                        <Col className={img.className} xs={img.xs}
                             md={img.md}>
                            <img src={img.children} width="100%"
                                 alt="img"/>
                        </Col>
                    </Row>
                )}
            </TabPane>
        );
    };

    render() {
        const {...props} = this.props;
        const {dataSource} = props;
        delete props.dataSource;
        delete props.isMobile;
        const tabsChildren = dataSource.block.children.map(this.getBlockChildren);
        return (
            <div {...props} {...dataSource.wrapper}>
                <div {...dataSource.page}>
                    <div {...dataSource.titleWrapper}>
                        {dataSource.titleWrapper.children.map(getChildrenToRender)}
                    </div>

                    <OverPack {...dataSource.OverPack}>
                        <div key="tabs">
                            <Tabs
                                key="tabs"
                                onChange={this.onChange}
                                activeKey={`${this.state.current}`}
                                {...dataSource.block}
                            >
                                {tabsChildren}
                            </Tabs>
                        </div>
                    </OverPack>
                </div>
            </div>
        );
    }
}

export default Content7;
